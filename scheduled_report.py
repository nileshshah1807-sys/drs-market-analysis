#!/usr/bin/env python3
"""
Scheduled Daily Email Report for DR. NILESH SHAH'S MARKET ANALYSIS
==================================================================
Sends the daily market report by email WITHOUT the app being open.

Windows Task Scheduler runs this script on weekdays at the time set in the app's
Settings tab (Settings > Auto Report Scheduling > "Install Windows Task").

Safety rules (shared with the in-app scheduler, so the report is never sent twice):
- Skips weekends and NSE trading holidays (holiday list fetched from NSE, cached per year)
- Sends at most once per day (auto_report_state.json)
- A lock file stops two copies running at the same time

Run manually:
    python scheduled_report.py            # respects all rules above
    python scheduled_report.py --force    # send now regardless
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime, date, timedelta
from pathlib import Path

from app_paths import FROZEN, DATA_DIR

BASE_DIR = DATA_DIR
SCHEDULE_FILE = BASE_DIR / "schedule_config.json"
WATCHLIST_FILE = BASE_DIR / "watchlist.json"
STATE_FILE = BASE_DIR / "auto_report_state.json"
LOCK_FILE = BASE_DIR / "auto_report.lock"
HOLIDAY_FILE = BASE_DIR / "nse_holidays.json"
LOG_FILE = BASE_DIR / "dr_shah_analysis.log"
TASK_NAME = "DR Nilesh Shah Daily Report"
LOCK_STALE_HOURS = 2

logger = logging.getLogger("scheduled_report")


# ------------------------------------------------------------
# Config / state
# ------------------------------------------------------------

def load_schedule() -> dict:
    config = {'enabled': False, 'hour': 18, 'minute': 0, 'report_type': 'Indian + US'}
    try:
        if SCHEDULE_FILE.exists():
            data = json.loads(SCHEDULE_FILE.read_text())
            config['enabled'] = bool(data.get('enabled', False))
            config['hour'] = int(data.get('hour', 18))
            config['minute'] = int(data.get('minute', 0))
            config['report_type'] = data.get('report_type', 'Indian + US')
    except Exception as e:
        logger.error(f"Schedule config load error: {e}")
    return config


def load_watchlist() -> list:
    try:
        data = json.loads(WATCHLIST_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def last_sent_date():
    try:
        return date.fromisoformat(json.loads(STATE_FILE.read_text()).get('last_sent', ''))
    except Exception:
        return None


def _mark_sent(today: date, detail: str):
    STATE_FILE.write_text(json.dumps({'last_sent': today.isoformat(), 'detail': detail,
                                      'at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, indent=2))


def _acquire_lock() -> bool:
    """Create the lock file atomically; clear it if left behind by a crashed run."""
    try:
        if LOCK_FILE.exists():
            age = datetime.now() - datetime.fromtimestamp(LOCK_FILE.stat().st_mtime)
            if age > timedelta(hours=LOCK_STALE_HOURS):
                LOCK_FILE.unlink()
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception as e:
        logger.warning(f"Lock error: {e}")
        return True


def _release_lock():
    try:
        LOCK_FILE.unlink()
    except OSError:
        pass


# ------------------------------------------------------------
# Trading-day check
# ------------------------------------------------------------

def _nse_holidays(year: int) -> set:
    """NSE equity trading holidays for a year (cached in nse_holidays.json). Empty set if unavailable."""
    cache = {}
    try:
        cache = json.loads(HOLIDAY_FILE.read_text())
        if str(year) in cache:
            return set(cache[str(year)])
    except Exception:
        pass
    try:
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://www.nseindia.com/resources/exchange-communication-holidays',
        }
        resp = requests.get('https://www.nseindia.com/api/holiday-master', params={'type': 'trading'},
                            headers=headers, timeout=20)
        days = []
        for h in resp.json().get('CM', []):
            d = datetime.strptime(h['tradingDate'], '%d-%b-%Y').date()
            if d.year == year:
                days.append(d.isoformat())
        if days:
            cache[str(year)] = days
            HOLIDAY_FILE.write_text(json.dumps(cache, indent=2))
        return set(days)
    except Exception as e:
        logger.warning(f"Could not fetch NSE holidays ({e}); only skipping weekends")
        return set()


def is_trading_day(day: date = None, india: bool = True):
    """(bool, reason). Weekends are never trading days; for Indian reports NSE holidays are skipped too."""
    day = day or date.today()
    if day.weekday() >= 5:
        return False, "weekend"
    if india and day.isoformat() in _nse_holidays(day.year):
        return False, "NSE holiday"
    return True, "trading day"


# ------------------------------------------------------------
# Send the report
# ------------------------------------------------------------

def run_scheduled_report(force: bool = False, watchlist: list = None, report_type: str = None,
                         max_late_hours: float = None):
    """Generate and email the daily report, following the schedule rules. Returns (sent: bool, message).

    max_late_hours: skip if it's this long past the scheduled time (the Windows task starts late
    when the PC was off or asleep; a report sent next morning would block that evening's one).
    """
    sched = load_schedule()
    today = date.today()
    report_type = report_type or sched['report_type']
    include_india = report_type != 'US Only'
    include_us = report_type != 'Indian Only'

    if not force:
        if not sched['enabled']:
            return False, "Auto-report is disabled in Settings"
        if last_sent_date() == today:
            return False, "Report already sent today"
        ok, reason = is_trading_day(today, india=include_india)
        if not ok:
            return False, f"Skipped: {reason}"
        if max_late_hours is not None:
            due = datetime.now().replace(hour=sched['hour'], minute=sched['minute'], second=0, microsecond=0)
            late = (datetime.now() - due).total_seconds() / 3600
            if late > max_late_hours or late < -0.25:
                return False, (f"Skipped: started at {datetime.now():%H:%M}, outside the window for the "
                               f"{sched['hour']:02d}:{sched['minute']:02d} report")

    if not _acquire_lock():
        return False, "Another report is already being generated"
    try:
        if not force and last_sent_date() == today:   # re-check after taking the lock
            return False, "Report already sent today"

        from daily_report import DailyReportGenerator
        generator = DailyReportGenerator()
        if not generator.email_config.is_configured:
            return False, "Email is not configured (Settings > Email Report Configuration)"

        watchlist = load_watchlist() if watchlist is None else watchlist
        report = generator.generate_report(watchlist={'NSE': watchlist} if (include_india and watchlist) else None,
                                           include_us=include_us, include_india=include_india)
        pdf_path = generator.generate_pdf_report(report)
        if generator.send_email_report(report, pdf_path):
            _mark_sent(today, report_type)
            return True, f"Report emailed to {', '.join(generator.email_config.receiver_emails)}"
        return False, f"Email failed: {generator.email_config.last_error}"
    except Exception as e:
        logger.exception("Scheduled report error")
        return False, f"Report failed: {e}"
    finally:
        _release_lock()


# ------------------------------------------------------------
# Windows Task Scheduler
# ------------------------------------------------------------

def _pythonw() -> str:
    """pythonw.exe runs without a console window; fall back to the current interpreter."""
    exe = Path(sys.executable)
    candidate = exe.with_name('pythonw.exe')
    return str(candidate if candidate.exists() else exe)


def _schtasks(*args):
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    return subprocess.run(['schtasks', *args], capture_output=True, text=True, creationflags=flags)


def install_task(hour: int, minute: int):
    """Create/replace a weekday Windows task at hour:minute. Returns (ok, message)."""
    if sys.platform != 'win32':
        return False, "Windows Task Scheduler is only available on Windows"
    if FROZEN:   # packaged .exe: the task runs the .exe itself in report-only mode (no window)
        command = subprocess.list2cmdline([sys.executable, '--scheduled-report'])
    else:
        command = subprocess.list2cmdline([_pythonw(), str(Path(__file__).resolve())])
    if len(command) > 261:
        return False, "Install path is too long for Task Scheduler (max 261 characters)"
    # Registered from XML (not /SC WEEKLY flags) so the task also runs on battery power and
    # starts late if the PC was off/asleep at the time - schtasks' defaults block both.
    xml_path = Path(os.environ.get('TEMP', str(BASE_DIR))) / 'dr_shah_task.xml'
    try:
        xml_path.write_text(_task_xml(hour, minute), encoding='utf-16')
        r = _schtasks('/Create', '/TN', TASK_NAME, '/XML', str(xml_path), '/F')
    finally:
        try:
            xml_path.unlink()
        except OSError:
            pass
    if r.returncode == 0:
        return True, f"Windows task installed: weekdays at {hour:02d}:{minute:02d}"
    return False, (r.stderr or r.stdout).strip()


def _task_xml(hour: int, minute: int) -> str:
    from xml.sax.saxutils import escape
    if FROZEN:
        program, arguments = sys.executable, '--scheduled-report'
    else:
        program, arguments = _pythonw(), subprocess.list2cmdline([str(Path(__file__).resolve())])
    domain, name = os.environ.get('USERDOMAIN', ''), os.environ.get('USERNAME', '')
    user = f"{domain}\\{name}" if domain else name
    start = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Emails the DR. NILESH SHAH'S MARKET ANALYSIS daily report on NSE trading days.</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start:%Y-%m-%dT%H:%M:%S}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <DaysOfWeek><Monday /><Tuesday /><Wednesday /><Thursday /><Friday /></DaysOfWeek>
        <WeeksInterval>1</WeeksInterval>
      </ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(user)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(program)}</Command>
      <Arguments>{escape(arguments)}</Arguments>
      <WorkingDirectory>{escape(str(BASE_DIR))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def remove_task():
    if sys.platform != 'win32':
        return False, "Not on Windows"
    r = _schtasks('/Delete', '/TN', TASK_NAME, '/F')
    if r.returncode == 0:
        return True, "Windows task removed"
    return False, (r.stderr or r.stdout).strip()


def task_status():
    """Next run time of the Windows task, or None if it isn't installed."""
    if sys.platform != 'win32':
        return None
    r = _schtasks('/Query', '/TN', TASK_NAME, '/FO', 'LIST')
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        if line.lower().startswith('next run time'):
            return line.split(':', 1)[1].strip()
    return "installed"


# ------------------------------------------------------------
# Command line (this is what the Windows task runs)
# ------------------------------------------------------------

def main():
    # pythonw has no console: send any print() output from the report modules to nowhere safely
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                        format='%(asctime)s - [Scheduled] %(message)s', filemode='a')
    import market_data   # noqa: F401 - captures yfinance's messages, keeping them out of the log
    force = '--force' in sys.argv
    sent, msg = run_scheduled_report(force=force, max_late_hours=3)
    logger.info(msg)
    print(msg)
    return 0 if sent or not msg.startswith(("Email failed", "Report failed")) else 1


if __name__ == "__main__":
    sys.exit(main())
