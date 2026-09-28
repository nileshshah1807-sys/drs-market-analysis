"""
Where the app keeps its files - works both as Python scripts and as a packaged .exe.

DATA_DIR      Your data: watchlist, settings, email config, reports, cache, log.
              Next to the .exe when packaged (so it survives restarts), otherwise
              next to these .py files.
RESOURCE_DIR  Read-only files shipped with the app (logo). Inside the .exe's
              temporary folder when packaged, otherwise next to these .py files.
"""

import sys
from pathlib import Path

FROZEN = bool(getattr(sys, 'frozen', False))
DATA_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', DATA_DIR))
