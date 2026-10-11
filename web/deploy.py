"""Publish the web version: push to GitHub, and Vercel puts it online by itself.
deploy_web.bat in the main folder runs this.

Each run: refreshes the NSE + BSE company list (for the search box), copies the scoring code
from the desktop app into web/api/_core, checks the web version on this PC (nothing is
published if a check fails), then commits and pushes to
GitHub (github.com/nileshshah1807-sys/drs-market-analysis, private). Vercel is connected to
that repository and deploys every push to `main` in about a minute.
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
SITE = "https://drs-market-analysis.vercel.app"


def say(text=''):
    print(text, flush=True)


def git(*args, **kw):
    return subprocess.run(['git', *args], cwd=ROOT, text=True, encoding='utf-8', errors='replace', **kw)


def main():
    say("DR. NILESH SHAH'S MARKET ANALYSIS - publish the web version (GitHub > Vercel)")
    say("=" * 78)

    say("\n[1/3] Updating the company list (NSE + BSE) and copying the scoring code...")
    r = subprocess.run([sys.executable, str(ROOT / 'symbols.py'), 'build'], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=ROOT)
    say("      " + (r.stdout.strip().splitlines()[-1] if r.returncode == 0 and r.stdout.strip()
                    else "couldn't download the lists just now - keeping the saved company list"))
    subprocess.run([sys.executable, str(WEB / 'sync_core.py')], check=True)

    say("\n[2/3] Checking the web version on this PC (about a minute)...")
    r = subprocess.run([sys.executable, str(WEB / 'tests' / 'test_web.py')], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    if r.returncode != 0:
        say(r.stdout[-3000:])
        say("The check found problems - nothing was published.")
        return 1
    say("      all checks passed")

    say("\n[3/3] Sending to GitHub...")
    git('add', '-A')
    if git('diff', '--cached', '--quiet').returncode != 0:
        if git('commit', '-q', '-m', f"Update {datetime.now():%d %b %Y %H:%M}").returncode != 0:
            say("Couldn't save the changes in git (see above).")
            return 1
    else:
        say("      no new changes to save")
    r = git('push', 'origin', 'main', capture_output=True)
    if r.returncode != 0:
        say(r.stdout + r.stderr)
        say("Couldn't send to GitHub (see above).")
        return 1
    say("      sent" if 'Everything up-to-date' not in (r.stdout + r.stderr) else "      GitHub already has everything")

    say(f"\nDone. Vercel updates the site in about a minute: {SITE}")
    say("Progress and history: https://vercel.com/dashboard > drs-market-analysis > Deployments")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
