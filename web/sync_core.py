"""Copy the desktop app's shared code into the web version (api/_core), so both score stocks
with exactly the same code - and the company list for the search box (public/symbols.json).
Run before every deploy (deploy_web.bat does it).

    python web/sync_core.py           copy
    python web/sync_core.py --check   only report whether the copies are up to date (exit 1 if not)
"""
import filecmp
import shutil
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent
DESKTOP = WEB.parent
CORE = WEB / 'api' / '_core'
SHARED = ['scoring.py', 'market_data.py', 'pattern_recognition.py', 'app_paths.py']
DATA = {'symbols_master.json': WEB / 'public' / 'symbols.json'}      # the NSE + BSE company list


def main():
    check = '--check' in sys.argv
    CORE.mkdir(parents=True, exist_ok=True)
    stale = [f for f in SHARED if not (CORE / f).exists() or not filecmp.cmp(DESKTOP / f, CORE / f, shallow=False)]
    stale += [f for f, dest in DATA.items() if not dest.exists() or not filecmp.cmp(DESKTOP / f, dest, shallow=False)]
    if check:
        print("web/api/_core is up to date" if not stale else f"out of date: {', '.join(stale)}")
        return 1 if stale else 0
    for f in SHARED:
        shutil.copy2(DESKTOP / f, CORE / f)
    for f, dest in DATA.items():
        shutil.copy2(DESKTOP / f, dest)
    (CORE / 'README.txt').write_text("Copied from the desktop app by web/sync_core.py - edit the originals in the "
                                     "main folder, not these copies.\n", encoding='utf-8')
    print(f"copied {len(SHARED) + len(DATA)} files into the web version" + (f" (updated: {', '.join(stale)})" if stale else " (no changes)"))
    return 0


if __name__ == '__main__':
    sys.exit(main())
