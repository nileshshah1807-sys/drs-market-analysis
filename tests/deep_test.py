"""Deep end-to-end test of DR. NILESH SHAH'S MARKET ANALYSIS.

Don't run this file directly - use run_tests.bat or tests/run_deep_test.py, which run it inside
a throwaway copy of the app. Nothing real is touched:
  - email goes to a fake mail server (nothing is sent)
  - Windows Task Scheduler calls are faked (your real scheduled task isn't changed)
  - dialogs are answered automatically, file dialogs point into the test folder
  - the email password is a dummy kept under a throwaway Credential Manager entry

Every feature is exercised and every error is recorded - including ones the app would
normally hide (logged errors, exceptions in background threads and Tk callbacks).
"""
import os, sys, time, json, csv, logging, threading, traceback, smtplib
from datetime import datetime, timedelta

sys.path.insert(0, os.getcwd())
OUT = os.path.join(os.getcwd(), '_test_out')
os.makedirs(OUT, exist_ok=True)

problems, passed, expected_warnings = [], [], []


# ---------- capture everything that goes wrong ----------
class ErrCapture(logging.Handler):
    def emit(self, record):
        msg = record.getMessage()
        if record.levelno >= logging.ERROR and 'division by zero' not in msg:
            problems.append(f"LOGGED ERROR: {msg[:200]}")


logging.getLogger().addHandler(ErrCapture())
threading.excepthook = lambda a: problems.append(
    f"THREAD EXCEPTION: {a.exc_type.__name__}: {a.exc_value}\n{''.join(traceback.format_tb(a.exc_traceback))[-600:]}")

# ---------- fake mail server ----------
sent = []


class FakeSMTP:
    def __init__(self, *a, **k): pass
    def ehlo(self): pass
    def starttls(self): pass
    def login(self, u, p): pass
    def send_message(self, msg): sent.append(msg)
    def quit(self): pass


smtplib.SMTP = smtplib.SMTP_SSL = FakeSMTP

import keyring
import daily_report
TEST_SERVICE = 'ZZ DR Nilesh Shah deep test - safe to delete'
daily_report.KEYRING_SERVICE = TEST_SERVICE
SENDER = json.load(open('email_config.json'))['sender_email']
keyring.set_password(TEST_SERVICE, SENDER, 'dummy-password-for-test')

import scheduled_report
_fake_task = {'on': False}
scheduled_report.install_task = lambda h, m: (True, f"(test) installed {h:02d}:{m:02d}")
scheduled_report.remove_task = lambda: (True, "(test) removed")
scheduled_report.task_status = lambda: "(test) next run" if _fake_task['on'] else None

import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import dr_shah_analysis as m
import score_history

dialog_log = []


def _info(title, msg, **k):
    dialog_log.append(('info', title, str(msg)))


def _warn(title, msg, **k):
    dialog_log.append(('warn', title, str(msg)))
    if expected_warnings:
        expected_warnings.pop()
    else:
        problems.append(f"UNEXPECTED WARNING DIALOG: {title}: {str(msg)[:160]}")


def _err(title, msg, **k):
    dialog_log.append(('error', title, str(msg)))
    problems.append(f"ERROR DIALOG: {title}: {str(msg)[:200]}")


messagebox.showinfo, messagebox.showwarning, messagebox.showerror = _info, _warn, _err
answers = {'askyesno': True, 'askyesnocancel': True}
messagebox.askyesno = lambda *a, **k: answers['askyesno']
messagebox.askyesnocancel = lambda *a, **k: answers['askyesnocancel']
simpledialog.askstring = lambda *a, **k: 'TestGroup'
paths = {'open': None, 'save': None}
filedialog.askopenfilename = lambda *a, **k: paths['open']
filedialog.asksaveasfilename = lambda *a, **k: paths['save']

root = tk.Tk()
root.report_callback_exception = lambda et, ev, tb: problems.append(
    f"TK CALLBACK EXCEPTION: {et.__name__}: {ev}\n{''.join(traceback.format_tb(tb))[-700:]}")
app = m.App(root)
COLS = list(app.tree['columns'])


def col(name):
    return COLS.index(name)


def cell(item, name):
    return str(app.tree.item(item)['values'][col(name)])


def wait(cond, timeout):          # use as:  yield wait(lambda: ..., seconds)
    return (cond, timeout)


def close_toplevels():
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            w.destroy()


def check(label, ok, detail=''):
    (passed if ok else problems).append(f"{'PASS' if ok else 'FAIL'} {label} {detail}".strip())


def is_number(text):
    try:
        float(str(text).replace('%', '').replace('+', '').replace(',', '').split()[0])
        return True
    except (ValueError, IndexError):
        return False


# ---------------- steps ----------------
def s_startup():
    tabs = [app.nb.tab(t, 'text').strip() for t in app.nb.tabs()]
    check('all tabs built', len(tabs) == 11, str(tabs))
    check('results table has new columns', 'vs Nifty 3M' in COLS and 'Score Chg' in COLS, str(COLS))
    yield wait(lambda: 'checking' not in app.task_status_lbl.cget('text'), 5)


def s_single_instance():
    first = m.single_instance_lock()          # main() isn't used by the test, so nothing holds it yet
    second = m.single_instance_lock()
    check('one copy at a time (second copy refused)', first is not None and second is None)
    yield None


def s_watchlist():
    orig = list(app.watchlist)
    app.entry.insert(0, 'm&m')
    app.add_stock()
    check('add stock (M&M)', 'M&M' in app.watchlist)
    rows = list(app.wl_list.get(0, tk.END))
    app.wl_list.selection_clear(0, tk.END)
    app.wl_list.selection_set(next(i for i, r in enumerate(rows) if app._wl_symbol(r) == 'M&M'))
    app.del_stock()
    check('delete stock', 'M&M' not in app.watchlist)
    app._create_group()
    check('create group', 'TestGroup' in app.watchlist_groups and app.group_var.get() == 'All Stocks')
    app._ask_group = lambda stock: 'TestGroup'            # the "which group?" dialog's answer
    app.wl_list.selection_clear(0, tk.END)
    app.wl_list.selection_set(0)
    first = app._wl_symbol(app.wl_list.get(0))
    app._add_to_group()
    check('add to group', first in app.watchlist_groups['TestGroup'])
    app.group_var.set('TestGroup')
    app._switch_group()
    check('switch group', app.wl_list.size() == 1, f"rows={app.wl_list.size()}")
    app.wl_list.selection_set(0)
    app._remove_from_group()
    check('remove from group', first not in app.watchlist_groups['TestGroup'])
    app.group_var.set('All Stocks')
    app._switch_group()
    for sector in ['Banking', 'IT', 'All']:
        app.sector_var.set(sector)
        app.refresh_watchlist()
    check('watchlist unchanged after ops', sorted(app.watchlist) == sorted(orig))
    yield None


def s_import_save_lists():
    orig = list(app.watchlist)
    files = {}
    files['csv'] = os.path.join(OUT, 'imp.csv')
    open(files['csv'], 'w').write("M&M\n20MICRONS\nBAJAJ-AUTO\n")
    files['txt'] = os.path.join(OUT, 'imp.txt')
    open(files['txt'], 'w').write("TCS\nINFY\n\n")
    files['json'] = os.path.join(OUT, 'imp.json')
    json.dump({'watchlist': ['HDFCBANK', 'ITC']}, open(files['json'], 'w'))
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws['A1'], ws['A2'], ws['A3'], ws['B2'] = 'Symbol', 'SBIN', '20MICRONS', 'M&M'
    files['xlsx'] = os.path.join(OUT, 'imp.xlsx')
    wb.save(files['xlsx'])
    from reportlab.pdfgen import canvas
    files['pdf'] = os.path.join(OUT, 'imp.pdf')
    c = canvas.Canvas(files['pdf'])
    c.drawString(100, 750, "WIPRO LT M&M BAJAJ-AUTO")
    c.save()
    expect = {'csv': {'M&M', '20MICRONS', 'BAJAJ-AUTO'}, 'txt': {'TCS', 'INFY'}, 'json': {'HDFCBANK', 'ITC'},
              'xlsx': {'SBIN', '20MICRONS', 'M&M'}, 'pdf': {'WIPRO', 'LT', 'M&M', 'BAJAJ-AUTO'}}
    for kind, fp in files.items():
        app.watchlist = []
        paths['open'] = fp
        app.import_list()
        check(f'import {kind}', expect[kind] == set(app.watchlist), f"got {sorted(app.watchlist)}")
    app.watchlist = orig
    app.refresh_watchlist()
    for ext in ('json', 'csv', 'txt'):
        paths['save'] = os.path.join(OUT, f'saved.{ext}')
        app.save_list()
        check(f'save list .{ext}', os.path.getsize(paths['save']) > 0)
    yield None


def s_scan():
    t0 = time.time()
    app.start_scan()
    yield wait(lambda: not app.scanning, 400)
    check('scan', len(app.results) >= len(app.watchlist) - 3, f"{len(app.results)}/{len(app.watchlist)} in {time.time()-t0:.0f}s")
    missing = sorted(set(app.watchlist) - {r['symbol'] for r in app.results})
    passed.append(f"INFO symbols with no data: {missing}")
    rs_ok = sum(1 for r in app.results if (r.get('rs') or {}).get('3M') is not None)
    check('relative strength vs Nifty', rs_ok >= 0.9 * len(app.results), f"{rs_ok}/{len(app.results)} stocks have a 3M figure")
    rows = score_history._read()
    today = datetime.now().strftime('%Y-%m-%d')
    check('score history saved', sum(1 for r in rows if r['date'] == today) == len(app.results), f"{len(rows)} rows")


def s_history_compare():
    """Pretend today's scan happened yesterday with one different signal, then scan again."""
    rows = score_history._read()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    target = app.results[0]['symbol']
    for row in rows:
        row['date'] = yesterday
        if row['symbol'] == target:
            row['rec'] = 'STRONG SELL' if row['rec'] != 'STRONG SELL' else 'STRONG BUY'
            row['score'] = '5.0' if row['rec'] == 'STRONG SELL' else '95.0'
    with open(score_history.HISTORY_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=score_history.FIELDS)
        w.writeheader()
        w.writerows(rows)
    n_dialogs = len(dialog_log)
    app.start_scan()
    yield wait(lambda: not app.scanning, 400)
    chg = [cell(i, 'Score Chg') for i in app.tree.get_children() if not cell(i, 'Recommendation').startswith('Error')]
    check('Score Chg vs previous day', sum(is_number(v) for v in chg) >= 0.9 * len(chg), f"{chg[:5]}")
    done = [d for d in dialog_log[n_dialogs:] if d[1] == 'Done']
    check('signal changes listed after scan', bool(done) and 'Signal changes' in done[-1][2] and target in done[-1][2],
          done[-1][2][:150].replace('\n', ' | ') if done else 'no Done dialog')
    r = next(x for x in app.results if x['symbol'] == target)
    app.update_breakdown(r)
    root.update()

    boxes = [w for w in app.bd_frame.winfo_children()
             if w.winfo_class() == 'Labelframe' and 'SCORE HISTORY' in str(w.cget('text'))]
    check('score history chart', bool(boxes) and any(c.winfo_class() == 'Canvas' for c in boxes[0].winfo_children()))


def s_results_table():
    n = len(app.tree.get_children())
    for rec in ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL", "All"]:
        app.result_filter_var.set(rec)
        app.filter_results()
    app.search_var.set(app.results[0]['symbol'][:3])
    root.update()
    app.search_var.set('')
    root.update()
    app.hide_illiquid_var.set(True)
    app.filter_results()
    app.hide_illiquid_var.set(False)
    app.filter_results()
    for c in COLS:
        app.sort_tree(c)
        app.sort_tree(c)
    app._sort_col = None
    app.sort_tree('Price')                    # ascending: numbers in order, any 'N/A' rows last
    prices = [cell(i, 'Price') for i in app.tree.get_children()]
    nums = [float(p) for p in prices if is_number(p)]
    check('numeric sort (text last)', nums == sorted(nums) and all(is_number(p) for p in prices[:len(nums)]))
    check('results filter/search/sort', len(app.tree.get_children()) == n)
    yield None


def s_details_every_stock():
    bad = []
    for r in app.results:
        try:
            app.update_breakdown(r)
            app.update_targets(r)
            app.update_patterns(r)
        except Exception as e:
            bad.append(f"{r['symbol']}: {type(e).__name__}: {e}")
    check('details tabs for every stock', not bad, str(bad[:3]))
    yield None


def s_exports():
    for name, fn, ext in [('excel', app.export_results, 'xlsx'), ('csv', app.export_results, 'csv'),
                          ('pdf', app.export_pdf, 'pdf')]:
        paths['save'] = os.path.join(OUT, f'results.{ext}')
        fn()
        check(f'export {name}', os.path.exists(paths['save']) and os.path.getsize(paths['save']) > 500)
    from openpyxl import load_workbook
    ws = load_workbook(os.path.join(OUT, 'results.xlsx')).active
    check('excel content', ws.max_row == len(app.results) + 1 and ws.cell(1, 12).value == 'Liquidity'
          and ws.cell(1, 14).value == 'vs Nifty 3M (%)', f"rows={ws.max_row}")
    yield None


def s_sector():
    app.analyze_sectors()
    yield wait(lambda: not getattr(app, '_sector_busy', False), 120)
    rows = [app.sector_tree.item(i)['values'] for i in app.sector_tree.get_children()]
    other = next((r[1] for r in rows if r[0] == 'Other'), 0)
    check('sector analysis', len(rows) >= 3 and other <= max(3, len(app.results) // 10),
          f"{len(rows)} sectors, 'Other'={other}")


def s_charts():
    app.tree.selection_set(app.tree.get_children()[0])
    for period in ['1mo', '3mo', '6mo', '1y', '2y']:
        app.chart_period_var.set(period)
        app.show_stock_chart()
        yield wait(lambda: any(w.winfo_class() == 'Canvas' for w in app.chart_frame.winfo_children()), 60)
        check(f'chart {period}', any(w.winfo_class() == 'Canvas' for w in app.chart_frame.winfo_children()))


def s_corporate():
    app.load_corporate_actions()
    yield wait(lambda: app.corp_status.cget('text').startswith(('Done', 'Error', 'Loaded')), 300)
    check('corporate scan', app.corp_status.cget('text').startswith('Done'), app.corp_status.cget('text')[:90])
    for f in ["All", "Upcoming", "Past", "Dividends", "Splits", "Bonus", "Rights", "Buyback", "All"]:
        app.corp_filter_var.set(f)
        app._filter_corporate_actions()
    for i in range(min(5, app.corp_listbox.size())):
        app.corp_listbox.selection_clear(0, tk.END)
        app.corp_listbox.selection_set(i)
        app.show_corporate_popup()
    close_toplevels()
    paths['save'] = os.path.join(OUT, 'corp.csv')
    app.export_corporate_csv()
    check('corporate CSV', os.path.exists(paths['save']))
    yield None


def s_backtest():
    for horizon, liquid in [('10 days', False), ('5 days', False), ('20 days', True)]:
        app.bt_horizon_var.set(horizon)
        app.bt_liquid_var.set(liquid)
        app._bt_result = None
        app.run_backtest()
        yield wait(lambda: str(app.bt_run_btn.cget('state')) == 'normal'
                   and (app._bt_result is not None or 'failed' in app.bt_status.cget('text')), 300)
        check(f'backtest {horizon} liquid={liquid}', app._bt_result is not None and len(app.bt_ind_tree.get_children()) == 10,
              app.bt_status.cget('text')[:80])
    app.bt_liquid_var.set(False)
    app.bt_horizon_var.set('10 days')
    app.run_backtest()
    yield wait(lambda: str(app.bt_run_btn.cget('state')) == 'normal' and app._bt_result is not None, 300)
    if app._bt_result and app._bt_result.get('suggested_weights'):
        suggested = dict(app._bt_result['suggested_weights'])
        app.apply_suggested_weights()
        yield wait(lambda: str(app.bt_run_btn.cget('state')) == 'normal', 120)
        meta = app._weights_meta()
        check('apply suggested weights (+ re-check record)', m.Scorer.WEIGHTS == suggested and meta.get('source') == 'backtest'
              and meta.get('horizon') == 10, str(meta)[:120])
        check('weights status line', 'SUGGESTED' in app.bt_weights_lbl.cget('text'), app.bt_weights_lbl.cget('text')[:90])
        app.recheck_weights()
        yield wait(lambda: not getattr(app, '_recheck_running', False), 300)
        meta = app._weights_meta()
        check('re-check weights', (meta.get('last_result') or {}).get('verdict') in ('ok', 'worse')
              and 'Re-check' in app.bt_weights_lbl.cget('text'), app.bt_weights_lbl.cget('text')[:120])
        app.reset_weights()
        check('reset weights', m.Scorer.WEIGHTS == m.Scorer.DEFAULT_WEIGHTS and app._weights_meta().get('source') == 'default')


def s_settings():
    app.save_email_config()
    check('save email config', daily_report.EmailConfig().is_configured)
    n = len(sent)
    app.test_email()
    check('test email (fake mail server)', len(sent) == n + 1)
    app.save_schedule()
    app.install_windows_task()
    _fake_task['on'] = True
    app._update_task_status()
    check('install task (faked)', 'INSTALLED' in app.task_status_lbl.cget('text'))
    app.remove_windows_task()
    _fake_task['on'] = False
    app.min_liquidity_var.set('1')
    app.save_liquidity_setting()
    expected_warnings.append(1)                # weights not totalling 100 must be refused
    app.weight_vars['rsi'].set(99)
    app.apply_weights()
    app.reset_weights()
    check('weights reset after invalid', m.Scorer.WEIGHTS == m.Scorer.DEFAULT_WEIGHTS)
    yield None


def s_reports():
    answers['askyesnocancel'] = False          # Indian market only
    app.generate_daily_report()
    yield wait(lambda: 'generated' in app.status_lbl.cget('text') or 'failed' in app.status_lbl.cget('text'), 400)
    check('daily report', 'generated' in app.status_lbl.cget('text'), app.status_lbl.cget('text'))
    n = len(sent)
    answers['askyesnocancel'] = True           # watchlist email
    app.send_email_report()
    yield wait(lambda: len(sent) > n or 'failed' in app.status_lbl.cget('text'), 200)
    ok = len(sent) > n and any(p.get_filename() for p in sent[-1].walk())
    html = sent[-1].get_payload()[0].get_payload(decode=True).decode('utf-8', 'ignore') if len(sent) > n else ''
    check('watchlist email (fake mail server)', ok and 'vs Nifty 3M' in html and 'Signal Changes' in html,
          app.status_lbl.cget('text'))
    n = len(sent)
    answers['askyesnocancel'] = False          # full market email
    app.send_email_report()
    yield wait(lambda: len(sent) > n or 'failed' in app.status_lbl.cget('text') or 'Error' in app.status_lbl.cget('text'), 500)
    check('full market email (fake mail server)', len(sent) > n, app.status_lbl.cget('text'))


def s_auto_report():
    now = time.localtime()
    json.dump({'enabled': True, 'hour': now.tm_hour, 'minute': now.tm_min, 'report_type': 'Indian Only'},
              open(m.SCHEDULE_FILE, 'w'))
    if os.path.exists(scheduled_report.STATE_FILE):
        os.remove(scheduled_report.STATE_FILE)
    n = len(sent)
    app._last_auto_report_date = None
    app._run_auto_report('Indian Only')
    yield wait(lambda: not app._auto_report_running, 400)
    trading, why = scheduled_report.is_trading_day()
    if trading:
        check('auto report sends', len(sent) == n + 1, app.status_lbl.cget('text'))
        ok2, msg2 = scheduled_report.run_scheduled_report()
        check('auto report not sent twice', not ok2 and 'already' in msg2, msg2)
    else:
        check('auto report skips non-trading day', len(sent) == n and why in app.status_lbl.cget('text'),
              app.status_lbl.cget('text'))
    json.dump({'enabled': True, 'hour': (now.tm_hour - 5) % 24, 'minute': 0, 'report_type': 'Indian Only'},
              open(m.SCHEDULE_FILE, 'w'))
    if os.path.exists(scheduled_report.STATE_FILE):
        os.remove(scheduled_report.STATE_FILE)
    ok3, msg3 = scheduled_report.run_scheduled_report(max_late_hours=3)
    check('late Windows-task run skipped', not ok3 and ('outside the window' in msg3 or 'Skipped' in msg3), msg3)


def s_misc():
    app.view_log()
    root.update()
    close_toplevels()
    root.event_generate('<F1>')
    app._on_escape()
    app._setup_market_status()
    app.update_dash()
    app.nb.select(app.help_tab)
    root.update()
    yield None


STEPS = [('startup', s_startup), ('one copy at a time', s_single_instance), ('watchlist', s_watchlist),
         ('import/save lists', s_import_save_lists), ('scan', s_scan), ('score history', s_history_compare),
         ('results table', s_results_table), ('details', s_details_every_stock), ('exports', s_exports),
         ('sector', s_sector), ('charts', s_charts), ('corporate', s_corporate), ('backtest', s_backtest),
         ('settings', s_settings), ('reports + email', s_reports), ('auto report', s_auto_report), ('misc', s_misc)]


class Driver:
    """Runs the steps inside Tk's main loop (background threads post results via root.after)."""
    def __init__(self):
        self.steps = iter(STEPS)
        self.gen = None
        self.waiting = None

    def tick(self):
        try:
            if self.gen is None:
                self.name, fn = next(self.steps)
                self.gen = fn()
                self.waiting = None
                print(f"... {self.name}", flush=True)
            if self.waiting:
                cond, timeout = self.waiting
                if not cond() and time.time() - self.wstart < timeout:
                    root.after(250, self.tick)
                    return
                if not cond():
                    problems.append(f"TIMEOUT in step '{self.name}' after {timeout}s")
            self.waiting = next(self.gen)
            self.wstart = time.time()
        except StopIteration:
            if self.gen is None:          # no more steps
                return finish()
            self.gen = None
        except Exception:
            problems.append(f"STEP CRASHED '{getattr(self, 'name', '?')}': {traceback.format_exc()[-900:]}")
            self.gen = None
        root.after(50, self.tick)


def finish():
    try:
        keyring.delete_password(TEST_SERVICE, SENDER)
    except Exception:
        pass
    print("\n".join(passed))
    print(f"\nemails captured by the fake mail server: {len(sent)} | dialogs: "
          f"{sum(1 for d in dialog_log if d[0] == 'info')} info, {sum(1 for d in dialog_log if d[0] == 'warn')} warning, "
          f"{sum(1 for d in dialog_log if d[0] == 'error')} error")
    print(f"\n==== PROBLEMS: {len(problems)} ====")
    print("\n".join(problems) if problems else "none")
    root.quit()


root.after(1500, Driver().tick)
root.mainloop()
try:
    root.destroy()
except Exception:
    pass
sys.exit(1 if problems else 0)
