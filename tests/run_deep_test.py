#!/usr/bin/env python3
"""
Run the deep end-to-end test of DR. NILESH SHAH'S MARKET ANALYSIS.

    python tests\\run_deep_test.py             normal Python
    python tests\\run_deep_test.py --exe-sim   as the packaged .exe (packages it leaves out are blocked)
    python tests\\run_deep_test.py --both      both (what run_tests.bat does)

Each run uses a throwaway copy of the app in your temp folder with a copy of your watchlist,
so your real data, email and Windows task are never touched. Needs internet (prices).
Takes about 5 minutes per run. Exit code 0 = everything passed.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
DATA_FILES = ['watchlist.json', 'watchlist_groups.json', 'app_settings.json', 'weights_config.json']
SAMPLE_WATCHLIST = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ITC', 'SBIN', 'PFC', 'GNFC', 'CREATIVE', 'NIFTYBEES']
NOISE = ('[AI]', '[EmailConfig]', '[PDF]', '[WARNING] scikit', 'DR. NILESH', 'Daily Market', '/5] ',
         '   Analyzed', '   Fetched', 'Report Generated', 'Market Sentiment', 'possibly delisted')


def make_sandbox(mode: str) -> Path:
    sandbox = Path(tempfile.gettempdir()) / f"drs_deep_test_{mode}"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir()
    for f in ROOT.glob('*.py'):
        shutil.copy2(f, sandbox)
    shutil.copy2(ROOT / 'logo_new.png', sandbox)
    for name in DATA_FILES:
        if (ROOT / name).exists():
            shutil.copy2(ROOT / name, sandbox)
    if not (sandbox / 'watchlist.json').exists():
        (sandbox / 'watchlist.json').write_text(json.dumps(SAMPLE_WATCHLIST))
    # test-only email settings (the password is a dummy, the mail server is faked)
    (sandbox / 'email_config.json').write_text(json.dumps({
        'smtp_server': 'smtp.example.com', 'smtp_port': 587, 'sender_email': 'deeptest@example.com',
        'receiver_emails': ['deeptest@example.com'], 'is_configured': True,
        'password_storage': 'windows_credential_manager'}))
    (sandbox / 'schedule_config.json').write_text(json.dumps(
        {'enabled': False, 'hour': 18, 'minute': 0, 'report_type': 'Indian Only'}))
    return sandbox


def run(mode: str) -> int:
    sandbox = make_sandbox(mode)
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    if mode == 'exe-sim':
        env['PYTHONPATH'] = str(TESTS / 'exe_sim')
    print(f"\n========== {mode.upper()} ==========  (test copy: {sandbox})", flush=True)
    t0 = time.time()
    proc = subprocess.Popen([sys.executable, '-u', str(TESTS / 'deep_test.py')], cwd=sandbox, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    lines = []
    for line in proc.stdout:
        line = line.rstrip()
        lines.append(line)
        if line.startswith('... '):
            print(f"  {line[4:]}", flush=True)            # progress: step names
    proc.wait()
    print()
    report = [l for l in lines if l.strip('= ') and not l.startswith('... ') and not any(n in l for n in NOISE)]
    print("\n".join(report))
    print(f"\n{mode}: finished in {(time.time() - t0) / 60:.1f} min - {'ALL PASSED' if proc.returncode == 0 else 'PROBLEMS FOUND'}")
    return proc.returncode


def main():
    modes = ['normal', 'exe-sim'] if '--both' in sys.argv else ['exe-sim'] if '--exe-sim' in sys.argv else ['normal']
    codes = [run(mode) for mode in modes]
    print("\nOVERALL:", "ALL PASSED" if not any(codes) else "PROBLEMS FOUND - see above")
    return 1 if any(codes) else 0


if __name__ == '__main__':
    sys.exit(main())
