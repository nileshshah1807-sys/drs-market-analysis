"""
Where the app keeps its files - works both as Python scripts and as a packaged .exe.

DATA_DIR      Your data: watchlist, settings, email config, reports, cache, log.
              Next to the .exe when packaged (so it survives restarts), otherwise
              next to these .py files.
RESOURCE_DIR  Read-only files shipped with the app (logo). Inside the .exe's
              temporary folder when packaged, otherwise next to these .py files.
"""

import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, 'frozen', False))
DATA_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', DATA_DIR))

if os.environ.get('VERCEL'):          # the web version: on Vercel only /tmp can be written (price cache)
    DATA_DIR = Path('/tmp/dr_shah')
    DATA_DIR.mkdir(exist_ok=True)


def pdf_logo(path, size=160):
    """The logo for a PDF page header, as a small copy. Drawn from the file itself, the
    full-size picture (1.5 MB) went into every report and made each PDF about 2 MB.
    Make it once per document and pass the result to drawImage()."""
    try:
        from PIL import Image
        from reportlab.lib.utils import ImageReader
        img = Image.open(path)
        img.thumbnail((size, size))
        return ImageReader(img)
    except Exception:
        return str(path)
