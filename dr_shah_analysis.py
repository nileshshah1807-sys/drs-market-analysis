#!/usr/bin/env python3
"""
DR. NILESH SHAH'S MARKET ANALYSIS - Professional Stock Technical Scanner
=========================================================================
Version 6.0 - Clean Version (No Live Trading)
"""

import sys
import os
import json

# A windowed .exe has no console: give print()/warnings somewhere harmless to write
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')
import csv
import threading
import time
import re
import queue
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Check Python version
if sys.version_info < (3, 7):
    print("ERROR: Python 3.7+ required!")
    input("Press Enter...")
    sys.exit(1)

# Third-party imports
try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
    import ta
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
except ImportError as e:
    print(f"Missing: {e}\nRun: pip install yfinance pandas numpy ta openpyxl")
    input("Press Enter...")
    sys.exit(1)

PDF_IMPORT_ERROR = ""
try:
    import pdfplumber
    PDF_OK = True
except Exception as e:   # not just ImportError: a missing native DLL raises OSError
    PDF_OK = False
    PDF_IMPORT_ERROR = f"{type(e).__name__}: {e}"

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Look and motion: the Daylight design, its dark mode, animations (ui_theme.py)
import ui_theme as ui

# Pattern Recognition
PATTERN_OK = False
try:
    from pattern_recognition import PatternDetector, PatternFormatter
    PATTERN_OK = True
except ImportError:
    pass

# Daily Report Module
REPORT_OK = False
try:
    from daily_report import DailyReportGenerator, EmailConfig
    REPORT_OK = True
except ImportError:
    pass

# Corporate Actions Module
CORPORATE_OK = False
try:
    from corporate_actions import CorporateActions
    CORPORATE_OK = True
except ImportError:
    pass

# Corporate Actions Engine (live NSE/BSE data)
CORP_ENGINE_OK = False
try:
    from corporate_actions_engine import CorporateActionsEngine
    CORP_ENGINE_OK = True
except ImportError:
    pass

# Indicators, the 0-100 score and stop-loss/targets (shared with the backtest and the daily report)
import scoring
from scoring import safe_float, Scorer, TargetCalc, relative_strength, NIFTY_SYMBOL, RS_PERIODS

try:
    import symbols          # every NSE + BSE company, for the "Add a stock" search
    SYMBOLS_OK = True
except ImportError:
    SYMBOLS_OK = False

# Fast batch price download + disk cache
MARKET_DATA_OK = False
try:
    import market_data
    MARKET_DATA_OK = True
except ImportError:
    pass

# Strategy backtester
BACKTEST_OK = False
try:
    import backtest
    BACKTEST_OK = True
except ImportError:
    pass

# Score history (score_history.csv: every scan, for "Score Chg" and the history chart)
HISTORY_OK = False
try:
    import score_history
    HISTORY_OK = True
except ImportError:
    pass

# Scheduled (Windows Task Scheduler) email report
SCHEDULER_OK = False
try:
    import scheduled_report
    SCHEDULER_OK = True
except ImportError:
    pass

# Try PIL
try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

# Try matplotlib for charts
try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.colors
    import matplotlib.ticker
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 - the 3D market map and sector chart
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

# Logging
from app_paths import FROZEN, DATA_DIR, RESOURCE_DIR, pdf_logo
log_file = str(DATA_DIR / 'dr_shah_analysis.log')
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s', filemode='a')
logger = logging.getLogger(__name__)
# yfinance's own error messages (e.g. every .NS miss for BSE-only stocks) are captured by
# market_data (to detect rate limiting) and kept out of the app log there

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = DATA_DIR                          # your data (next to the .exe when packaged)
LOGO_PATH = RESOURCE_DIR / "logo_new.png"    # bundled inside the .exe when packaged
WATCHLIST_FILE = BASE_DIR / "watchlist.json"
SCHEDULE_FILE = BASE_DIR / "schedule_config.json"
WEIGHTS_FILE = BASE_DIR / "weights_config.json"
APP_SETTINGS_FILE = BASE_DIR / "app_settings.json"
DEFAULT_MIN_LIQUIDITY_CR = 1.0   # stocks trading less than this (Rs crore/day) are flagged as illiquid
HISTORY_YEARS = 5   # years of price history kept in the disk cache (scans use the last 2y; backtests use all)
LOG_FILE = BASE_DIR / "dr_shah_analysis.log"

SECTOR_MAP = {
    'Banking': ['HDFCBANK', 'ICICIBANK', 'SBIN', 'KOTAKBANK', 'AXISBANK', 'INDUSINDBK', 'FEDERALBNK', 'BANDHANBNK', 'IDFCFIRSTB', 'PNB', 'BANKBARODA', 'CANBK', 'UNIONBANK'],
    'IT': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTIM', 'MPHASIS', 'COFORGE', 'PERSISTENT', 'LTTS'],
    'Auto': ['MARUTI', 'TATAMOTORS', 'TMPV', 'TMCV', 'BAJAJ-AUTO', 'HEROMOTOCO', 'EICHERMOT', 'M&M', 'TVSMOTOR', 'BAJFINANCE', 'BAJAJFINSV', 'ESCORTS'],
    'Pharma': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'LUPIN', 'BIOCON', 'TORNTPHARM', 'ALKEM', 'GLENMARK'],
    'FMCG': ['HINDUNILVR', 'ITC', 'NESTLEIND', 'BRITANNIA', 'DABUR', 'MARICO', 'GODREJCP', 'TATACONSUM', 'COLPAL'],
    'Energy': ['RELIANCE', 'ONGC', 'BPCL', 'POWERGRID', 'NTPC', 'GAIL', 'IOC', 'HINDPETRO', 'TATAPOWER'],
    'Metals': ['TATASTEEL', 'JSWSTEEL', 'HINDALCO', 'VEDL', 'NATIONALUM', 'JINDALSTEL', 'SAIL', 'NMDC'],
    'Infra': ['LT', 'ADANIENT', 'ADANIPORTS', 'ADANIENSOL', 'GMRINFRA', 'IRCON', 'RVNL', 'NBCC'],
    'Telecom': ['BHARTIARTL', 'IDEA', 'INDUSTOWER', 'HFCL'],
    'Chemicals': ['PIDILITIND', 'ASIANPAINT', 'BERGEPAINT', 'SRF', 'DEEPAKNTR', 'ATUL', 'NAVINFLUOR'],
}

THEME = ui.palette('light')   # the active colours; App switches it to dark mode if that's chosen in Settings


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

class DataCache:
    def __init__(self, hours=4):
        self.cache = {}
        self.duration = timedelta(hours=hours)
        self._lock = threading.Lock()
    
    def get(self, key):
        with self._lock:
            if key in self.cache:
                data, ts = self.cache[key]
                if datetime.now() - ts < self.duration:
                    return data
                del self.cache[key]
        return None
    
    def set(self, key, data):
        with self._lock:
            self.cache[key] = (data, datetime.now())
    
    def clear(self):
        with self._lock:
            self.cache.clear()
    
    def count(self):
        with self._lock:
            return len(self.cache)


class ThreadSafeGUI:
    def __init__(self, root):
        self.root = root
        self.queue = queue.Queue()
        self._process()
    
    def _process(self):
        try:
            while True:
                func, args, kwargs = self.queue.get_nowait()
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    # One failing update must not stop the queue from being processed
                    logger.error(f"GUI update error in {getattr(func, '__name__', func)}: {e}")
        except queue.Empty:
            pass
        self.root.after(40, self._process)
    
    def schedule(self, func, *args, **kwargs):
        self.queue.put((func, args, kwargs))


# ============================================================
# TECHNICAL ANALYZER
# ============================================================

class Analyzer:
    def __init__(self):
        self.cache = DataCache(4)
        self.listing_days = {}   # new listings in the last fetch_many: symbol -> their daily candles
        self.pattern_detector = PatternDetector() if PATTERN_OK else None

    def fetch(self, symbol, period="2y"):
        key = f"{symbol}_{period}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        if MARKET_DATA_OK:
            df = market_data.load_scan_history([symbol], years=HISTORY_YEARS).get(symbol.upper())
            # 20 candles of history in all - not 20 inside the period: a month with holidays has
            # as few as 17 trading days, and its chart used to come back as "No data"
            if df is not None and len(df) >= 20:
                df = market_data.slice_period(df, period)
                self.cache.set(key, df)
                return df
            return pd.DataFrame()

        for suffix in ['.NS', '.BO']:
            try:
                ticker = yf.Ticker(f"{symbol}{suffix}")
                df = ticker.history(period=period)
                if df is not None and not df.empty and len(df) >= 20:
                    self.cache.set(key, df)
                    return df
            except:
                continue
        return pd.DataFrame()

    def fetch_many(self, symbols, period="2y", progress=None):
        """Fetch many symbols at once (one batch download + disk cache). Returns {symbol: df}.
        Stocks listed within the last month come back with 1-hour candles instead of daily
        ones; their daily candles are kept in self.listing_days (see analyze)."""
        if not MARKET_DATA_OK:
            out = {}
            for s in symbols:
                df = self.fetch(s, period)
                if df is not None and not df.empty:
                    out[s] = df
            return out
        days = {}
        data = market_data.load_scan_history(symbols, years=HISTORY_YEARS, progress=progress, days=days)
        self.listing_days = {s: days[s.upper()] for s in symbols if s.upper() in days}
        out = {}
        for s in symbols:
            df = data.get(s.upper())
            if df is not None:
                df = market_data.slice_period(df, period)
                if len(df) >= 20:
                    out[s] = df
                    self.cache.set(f"{s}_{period}", df)
                elif market_data.is_hourly(df):
                    out[s] = df   # listed a day or two ago: too few candles yet (the scan says so)
        return out

    def analyze(self, df, days=None):
        """`days`: a new listing's daily candles, when `df` holds its 1-hour candles (worked
        out from `df` if not given)."""
        data = scoring.indicators(df, days)

        # Pattern Detection
        patterns = {}
        if self.pattern_detector:
            try: patterns = self.pattern_detector.detect_all_patterns(df)
            except Exception as e:
                logger.warning(f"Pattern detection error: {e}")
                patterns = {'chart': [], 'candlestick': [], 'harmonic': [], 'summary': {}}
        
        data['patterns'] = patterns
        return data


# Relative strength vs the Nifty 50 lives in scoring.py (shared with the web version)


ROTATION_DAYS = 7     # a sector's score is compared with its stocks' scans from about this many days earlier
ROTATION_FLAT = 1.0   # points: a smaller move in a sector's average score counts as no change


def sector_rotation(avg, change, benchmark):
    """Where a sector stands, from its strength AND its direction:

        LEADING    stronger than the watchlist's average and not falling
        WEAKENING  stronger than average, but its score is falling
        IMPROVING  weaker than average, but its score is rising
        LAGGING    weaker than average and not rising

    `change`: move in the sector's average score since the earlier scan, None if there is none
    (direction unknown: strength alone then decides between LEADING and LAGGING)."""
    strong = avg >= benchmark
    if change is None:
        return "LEADING" if strong else "LAGGING"
    if strong:
        return "WEAKENING" if change < -ROTATION_FLAT else "LEADING"
    return "IMPROVING" if change > ROTATION_FLAT else "LAGGING"


def market_status(now, holidays=None):
    """(is it open, text for the light) for the NSE cash market at `now` - this PC's clock, taken
    to be Indian time. Open 09:15-15:30 on weekdays that aren't NSE holidays.
    `holidays`: set of 'YYYY-MM-DD' (None if the list isn't known - weekends only are then closed)."""
    if now.weekday() >= 5:
        return False, "Market closed"
    if holidays and now.strftime('%Y-%m-%d') in holidays:
        return False, "Market closed: NSE holiday"
    minutes = now.hour * 60 + now.minute
    if 9 * 60 + 15 <= minutes <= 15 * 60 + 30:
        return True, "Market open"
    return False, "Market closed"




# ============================================================
# SETTINGS & SCORING WEIGHTS (shared by the app and scripts)
# ============================================================

def load_app_settings():
    try:
        if APP_SETTINGS_FILE.exists():
            with open(APP_SETTINGS_FILE, 'r') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error(f"Could not load app settings: {e}")
    return {}


def write_json(path, data, **kw):
    """Write a JSON file completely or not at all. Written in place, a crash or power cut
    mid-write leaves the file cut short - and a watchlist that can't be read loads as empty."""
    tmp = str(path) + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, **kw)
    os.replace(tmp, path)


def save_app_settings(settings):
    write_json(APP_SETTINGS_FILE, settings, indent=2)


def save_weights(weights, meta=None):
    """Use these weights for scoring from now on and remember them (weights_config.json).
    `meta` records where they came from (default / manual / backtest) for the monthly re-check."""
    Scorer.WEIGHTS.update(weights)
    with open(WEIGHTS_FILE, 'w') as f:
        json.dump(weights, f, indent=2)
    settings = load_app_settings()
    settings['weights_meta'] = meta or {'source': 'manual', 'applied': datetime.now().strftime('%Y-%m-%d')}
    save_app_settings(settings)


# ============================================================
# ONE COPY AT A TIME
# ============================================================

APP_TITLE = "DR. NILESH SHAH'S MARKET ANALYSIS"


def single_instance_lock():
    """Stops a second copy of the app (e.g. the .exe and the Python version) running on the
    same data folder - both would save the watchlist/settings and overwrite each other's changes.
    Returns a lock to keep for the app's lifetime, or None if another copy is already running."""
    name = "DRNileshShahMarketAnalysis-" + hashlib.md5(str(DATA_DIR).lower().encode('utf-8')).hexdigest()[:16]
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            return True                       # couldn't check - don't block the app
        if ctypes.get_last_error() == 183:    # ERROR_ALREADY_EXISTS: another copy holds it
            kernel32.CloseHandle(handle)
            return None
        return handle                         # released automatically when the app exits
    lock = DATA_DIR / ".app.lock"             # other systems: a lock file with our process id
    try:
        os.kill(int(lock.read_text()), 0)
        return None
    except (OSError, ValueError):
        lock.write_text(str(os.getpid()))
        return lock


def focus_running_app():
    """Bring the already-running copy's window to the front. True if found."""
    if sys.platform != 'win32':
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.FindWindowW.restype = wintypes.HWND
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        hwnd = user32.FindWindowW(None, APP_TITLE)
        if not hwnd:
            return False
        user32.ShowWindow(hwnd, 9)            # SW_RESTORE (un-minimise)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tw = None
        widget.bind("<Enter>", self.show, add='+')
        widget.bind("<Leave>", self.hide, add='+')
    
    def show(self, e=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tw, text=self.text, bg=THEME['fg'], fg=THEME['bg2'], justify=tk.LEFT,
                 font=(ui.FONT, 9), padx=10, pady=6).pack()
    
    def hide(self, e=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None


# ============================================================
# MAIN APP
# ============================================================

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("DR. NILESH SHAH'S MARKET ANALYSIS")
        self.root.geometry("1600x1000")
        self.root.minsize(1400, 900)
        self.root.configure(bg=THEME['bg'])
        
        try:
            if LOGO_PATH.exists():
                # iconbitmap() only accepts .ico files; iconphoto() works with PNG
                self._icon_img = tk.PhotoImage(file=str(LOGO_PATH))
                self.root.iconphoto(True, self._icon_img)
        except: pass
        
        self.analyzer = Analyzer()
        self.scorer = Scorer()
        self.gui = ThreadSafeGUI(root)
        self.watchlist = []
        self.results = []
        self.scanning = False
        
        self.watchlist_groups = {'All Stocks': [], 'Favorites': [], 'Swing Trades': [], 
                                 'Long Term': [], 'Dividend Picks': [], 'Momentum': []}
        self.current_group = 'All Stocks'
        self._scroll_canvases = []
        self._last_auto_report_date = None
        self._auto_report_running = False
        self.load_watchlist()
        self.load_watchlist_groups()
        self._load_weights()
        settings = self._load_app_settings()
        self.min_liquidity_cr = settings.get('min_liquidity_cr', DEFAULT_MIN_LIQUIDITY_CR)
        # Look: Daylight (light) or its dark mode, and animations - Settings > Appearance
        THEME.clear()
        THEME.update(ui.palette(settings.get('appearance', 'light')))
        ui.init_fonts(root)
        ui.Motion.enabled = bool(settings.get('animations', True)) and ui.windows_allows_animation()
        ui.style_ttk(root, THEME)
        self.markers = ui.marker_images(THEME)
        self.build_ui()
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.refresh_watchlist()
        self.center()
        self._setup_market_status()
        self._refresh_holidays()
        if SYMBOLS_OK:    # the NSE + BSE company list is downloaded again when it's over a week old
            threading.Thread(target=self._refresh_companies, daemon=True).start()
        self.root.after(30000, self._check_auto_report)
        self.root.after(120000, self._auto_recheck_weights)   # monthly re-check of backtest weights
        logger.info("App started v7.0")
    
    def center(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        self.root.geometry(f"{w}x{h}+{(self.root.winfo_screenwidth()-w)//2}+{(self.root.winfo_screenheight()-h)//2}")
    
    def btn(self, parent, text, color, cmd, kind=None, **kw):
        """A raised button (ui.RoundButton). `color` is the colour the app used to pass: the
        accent colour makes a primary button, a danger colour a danger button, anything else a
        quiet secondary one - so the window isn't a rainbow of buttons."""
        T = THEME
        if kind is None:
            kind = 'primary' if color == T['accent'] else 'danger' if color in (T['danger'], T['danger2']) else 'secondary'
        return ui.RoundButton(parent, text, command=cmd, kind=kind, theme=T)

    def build_ui(self):
        T = THEME
        self.root.configure(bg=T['bg'])

        # HEADER: logo and name, market light, file actions
        header = tk.Frame(self.root, bg=T['bg2'], height=72)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Frame(self.root, bg=T['line'], height=1).pack(fill=tk.X)

        logo_frame = tk.Frame(header, bg=T['bg2'])
        logo_frame.pack(side=tk.LEFT, padx=(20, 12))
        try:
            if LOGO_PATH.exists() and PIL_OK:
                img = Image.open(str(LOGO_PATH))
                img.thumbnail((100, 50), Image.Resampling.LANCZOS)   # keeps its shape (it used to be squashed square)
                self.logo_img = ImageTk.PhotoImage(img)
                tk.Label(logo_frame, image=self.logo_img, bg=T['bg2']).pack()
        except Exception:
            pass

        title_frame = tk.Frame(header, bg=T['bg2'])
        title_frame.pack(side=tk.LEFT)
        tk.Label(title_frame, text="DR. NILESH SHAH'S MARKET ANALYSIS", bg=T['bg2'], fg=T['fg'],
                 font=(ui.DISPLAY, 18, 'bold')).pack(anchor=tk.W)
        tk.Label(title_frame, text="Technical scanner for NSE and BSE stocks", bg=T['bg2'], fg=T['fg3'],
                 font=(ui.FONT, 10)).pack(anchor=tk.W)

        btn_row = tk.Frame(header, bg=T['bg2'])
        btn_row.pack(side=tk.RIGHT, padx=(8, 20))
        for text, cmd in (("Import", self.import_list), ("Save", self.save_list), ("Excel", self.export_results),
                          ("PDF", self.export_pdf), ("Report", self.generate_daily_report), ("Email", self.send_email_report)):
            self.btn(btn_row, text, None, cmd, kind='ghost').pack(side=tk.RIGHT, padx=3)

        market_frame = tk.Frame(header, bg=T['bg2'])
        market_frame.pack(side=tk.RIGHT, padx=18)
        self.market_dot = tk.Canvas(market_frame, width=18, height=18, bg=T['bg2'], highlightthickness=0)
        self.market_dot.pack(side=tk.LEFT, padx=(0, 4))
        self.market_dot.create_oval(5, 5, 13, 13, fill=T['fg3'], outline='', tags='dot')
        self.market_status_lbl = tk.Label(market_frame, text="Market closed", bg=T['bg2'], fg=T['fg2'], font=(ui.FONT, 10))
        self.market_status_lbl.pack(side=tk.LEFT)

        # SCAN SUMMARY: one raised card (numbers count up and the bar grows after a scan)
        self.summary = ui.SummaryCard(self.root, T)
        self.summary.pack(fill=tk.X, padx=16, pady=(12, 2))

        # CONTROLS: add stocks, scan
        ctrl = tk.Frame(self.root, bg=T['bg2'], highlightbackground=T['line'], highlightthickness=1)
        ctrl.pack(fill=tk.X, padx=16, pady=(8, 10))

        wl = tk.Frame(ctrl, bg=T['bg2'])
        wl.pack(side=tk.LEFT, padx=16, pady=10)
        tk.Label(wl, text="Add a stock: type the company's name or its symbol", bg=T['bg2'], fg=T['fg2'],
                 font=(ui.FONT, 9)).grid(row=0, column=0, sticky='w', pady=(0, 3))
        self.entry = tk.Entry(wl, font=(ui.FONT, 11), bg=T['input'], fg=T['fg'], insertbackground=T['fg'], relief=tk.FLAT,
                              width=30, highlightbackground=T['line'], highlightcolor=T['accent'], highlightthickness=1)
        self.entry.grid(row=1, column=0, ipady=6, padx=(0, 8))
        self.entry.bind('<Return>', lambda e: self.add_stock())
        # Matching companies drop down while typing, each with its NSE and BSE symbols
        self.suggest = ui.SuggestBox(self.entry, T, self._company_rows, self._add_company,
                                     columns=(('Company', 360), ('NSE symbol', 150), ('BSE symbol (code)', 190)),
                                     empty_text="No company found. Check the spelling - or, for a stock listed in the last few days,\n"
                                                "type its exchange symbol and press Enter.") if SYMBOLS_OK else None
        self.btn(wl, "Add", None, self.add_stock).grid(row=1, column=1, padx=3)
        self.btn(wl, "Delete", T['danger'], self.del_stock).grid(row=1, column=2, padx=3)
        self.btn(wl, "Clear", T['danger'], self.clear_list).grid(row=1, column=3, padx=3)
        tk.Label(wl, text="Sector", bg=T['bg2'], fg=T['fg2'], font=(ui.FONT, 9)).grid(row=0, column=4, sticky='w', padx=(20, 0), pady=(0, 3))
        self.sector_var = tk.StringVar(value="All")
        sector_cb = ttk.Combobox(wl, textvariable=self.sector_var, values=["All"] + list(SECTOR_MAP.keys()), state='readonly', width=13)
        sector_cb.grid(row=1, column=4, padx=(20, 0), ipady=2)
        sector_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_watchlist())
        Tooltip(sector_cb, "Filter the watchlist by sector")

        scan = tk.Frame(ctrl, bg=T['bg2'])
        scan.pack(side=tk.RIGHT, padx=16, pady=10)
        self.scan_btn = self.btn(scan, "Scan all stocks", None, self.start_scan, kind='primary')
        self.scan_btn.pack(side=tk.LEFT, padx=(0, 16))
        Tooltip(self.scan_btn, "Scan all stocks (F5)")
        prog = tk.Frame(scan, bg=T['bg2'])
        prog.pack(side=tk.LEFT)
        self.progress = ttk.Progressbar(prog, mode='determinate', length=240, style='Accent.Horizontal.TProgressbar')
        self.progress.pack(anchor=tk.W, pady=(4, 6))
        self.status_lbl = tk.Label(prog, text="Ready", bg=T['bg2'], fg=T['fg2'], font=(ui.FONT, 9), anchor='w', width=48)
        self.status_lbl.pack(anchor=tk.W)

        # STATUS BAR (packed before the tabs, at the bottom, so a tall table can't push it off the window)
        status = tk.Frame(self.root, bg=T['bg2'], height=28, highlightbackground=T['line'], highlightthickness=1)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        status.pack_propagate(False)
        self.last_scan_lbl = tk.Label(status, text="Last scan: never", bg=T['bg2'], fg=T['fg3'], font=(ui.FONT, 9))
        self.last_scan_lbl.pack(side=tk.LEFT, padx=16)
        self.cache_lbl = tk.Label(status, text="Cache: 0", bg=T['bg2'], fg=T['fg3'], font=(ui.FONT, 9))
        self.cache_lbl.pack(side=tk.LEFT, padx=16)
        tk.Label(status, text="F5 scan   Ctrl+I import   Del delete   F1 help", bg=T['bg2'], fg=T['fg3'],
                 font=(ui.FONT, 9)).pack(side=tk.RIGHT, padx=16)

        # TABS: the notebook's own tabs are hidden; ui.TabBar draws them with a sliding underline
        nb_frame = tk.Frame(self.root, bg=T['bg'])
        nb_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))
        tab_holder = tk.Frame(nb_frame, bg=T['bg2'])
        tab_holder.pack(fill=tk.X)
        self.nb = ttk.Notebook(nb_frame, style='Tabless.TNotebook')
        self.nb.pack(fill=tk.BOTH, expand=True)

        self.build_watchlist_tab()
        self.build_results_tab()
        self.build_breakdown_tab()
        self.build_targets_tab()
        self.build_patterns_tab()
        self.build_corporate_tab()
        self.build_charts_tab()
        self.build_sector_tab()
        self.build_backtest_tab()
        self.build_settings_tab()
        self.build_help_tab()
        self.tabbar = ui.TabBar(tab_holder, self.nb, T)
        self.tabbar.pack(fill=tk.X)


        # Shortcuts
        self.root.bind('<F5>', lambda e: self.start_scan())
        self.root.bind('<Control-i>', lambda e: self.import_list())
        self.root.bind('<Control-s>', lambda e: self.save_list())
        self.root.bind('<Delete>', lambda e: None if self._typing_in(e.widget) else self.del_stock())
        self.root.bind('<Control-e>', lambda e: self.export_results())
        self.root.bind('<Control-p>', lambda e: self.export_pdf())
        self.root.bind('<Control-d>', lambda e: self.generate_daily_report())
        self.root.bind('<Control-g>', lambda e: self._create_group())
        self.root.bind('<Control-f>', lambda e: self.search_entry.focus_set() if hasattr(self, 'search_entry') else None)
        self.root.bind('<Escape>', lambda e: self._on_escape())
        self.root.bind('<Control-a>', lambda e: self._select_all_results())
        self.root.bind('<Control-l>', lambda e: self.view_log())
        self.root.bind('<F1>', lambda e: self.nb.select(self.help_tab))

        ui.skin(self.root, T)
        ui.set_titlebar(self.root, T['mode'] == 'dark')

    def build_watchlist_tab(self):
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Watchlist  ")
        
        # Groups bar
        groups_bar = tk.Frame(tab, bg=T['bg2'], height=50)
        groups_bar.pack(fill=tk.X)
        groups_bar.pack_propagate(False)
        
        tk.Label(groups_bar, text="Group", bg=T['bg2'], fg=T['fg2'], font=(ui.FONT, 10)).pack(side=tk.LEFT, padx=(14, 6))
        self.group_var = tk.StringVar(value='All Stocks')
        self.group_cb = ttk.Combobox(groups_bar, textvariable=self.group_var, 
                                     values=list(self.watchlist_groups.keys()), state='readonly', width=15)
        self.group_cb.pack(side=tk.LEFT, padx=5)
        self.group_cb.bind('<<ComboboxSelected>>', lambda e: self._switch_group())
        self.btn(groups_bar, "New Group", T['accent'], self._create_group).pack(side=tk.LEFT, padx=4)
        self.btn(groups_bar, "Add to Group", T['success'], self._add_to_group).pack(side=tk.LEFT, padx=4)
        self.btn(groups_bar, "Remove", T['warning'], self._remove_from_group).pack(side=tk.LEFT, padx=4)
        self.group_count_lbl = tk.Label(groups_bar, text="", bg=T['bg2'], fg=T['fg3'], font=(ui.FONT, 9))
        self.group_count_lbl.pack(side=tk.RIGHT, padx=10)
        
        # Main list
        list_frame = tk.Frame(tab, bg=T['bg'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        sb = ttk.Scrollbar(list_frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.wl_list = tk.Listbox(list_frame, font=(ui.FONT, 12), yscrollcommand=sb.set)
        self.wl_list.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.wl_list.yview)
        self.wl_count = tk.Label(tab, text="Stocks: 0", bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 10))
        self.wl_count.pack(pady=5)

    def build_results_tab(self):
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Scan Results  ")
        
        cols = ('Symbol', 'Price', 'Change%', 'vs Nifty 3M', 'RSI', 'SuperTrend', 'VWAP', 'Score', 'Score Chg',
                'Recommendation', '52W High', '52W Low', 'ATR', 'Traded/day (Cr)', 'Candle')
        col_widths = {'Symbol': 110, 'Price': 90, 'Change%': 80, 'vs Nifty 3M': 95, 'RSI': 60, 'SuperTrend': 90,
                      'VWAP': 85, 'Score': 65, 'Score Chg': 80, 'Recommendation': 120, '52W High': 90,
                      '52W Low': 90, 'ATR': 70, 'Traded/day (Cr)': 115, 'Candle': 70}
        text_cols = ('Symbol', 'SuperTrend', 'VWAP', 'Recommendation', 'Candle')   # left-aligned; numbers right-aligned
        
        # Search bar above results
        search_frame = tk.Frame(tab, bg=T['bg'])
        search_frame.pack(fill=tk.X, padx=2, pady=(12, 0))
        
        tk.Label(search_frame, text="Find", bg=T['bg'], fg=T['fg2'], font=(ui.FONT, 10)).pack(side=tk.LEFT, padx=(4, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *args: self.filter_results())  # trace('w') was removed in Tk 9
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, bg=T['input'], fg=T['fg'],
                                     insertbackground=T['fg'], font=(ui.FONT, 10), width=26, relief=tk.FLAT,
                                     highlightbackground=T['line'], highlightcolor=T['accent'], highlightthickness=1)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 6), ipady=5)
        Tooltip(self.search_entry, "Type to filter results by symbol")
        
        self.btn(search_frame, "Clear", None, lambda: self.search_var.set("")).pack(side=tk.LEFT, padx=4)
        
        tk.Label(search_frame, text="Show", bg=T['bg'], fg=T['fg2'], font=(ui.FONT, 10)).pack(side=tk.LEFT, padx=(22, 6))
        self.result_filter_var = tk.StringVar(value="All")
        filter_cb = ttk.Combobox(search_frame, textvariable=self.result_filter_var,
                                values=["All", "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"],
                                state='readonly', width=15)
        filter_cb.pack(side=tk.LEFT, padx=4, ipady=2)
        filter_cb.bind("<<ComboboxSelected>>", lambda e: self.filter_results())

        self.hide_illiquid_var = tk.BooleanVar(value=False)
        self.hide_illiquid_cb = tk.Checkbutton(search_frame, variable=self.hide_illiquid_var, command=self.filter_results,
                                               text=f"Hide illiquid (< Rs {self.min_liquidity_cr:g} Cr/day)",
                                               bg=T['bg'], fg=T['fg'], selectcolor=T['input'], activebackground=T['bg'],
                                               activeforeground=T['fg'], font=(ui.FONT, 10))
        self.hide_illiquid_cb.pack(side=tk.LEFT, padx=(22, 5))
        Tooltip(self.hide_illiquid_cb, "Illiquid stocks: stop-loss and targets are unreliable because\n"
                                       "prices can gap and orders may not fill. Threshold is set in Settings.")
        
        frame = tk.Frame(tab, bg=T['line'], padx=1, pady=1)     # 1px border round the table
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=10)
        inner = tk.Frame(frame, bg=T['card'])
        inner.pack(fill=tk.BOTH, expand=True)
        
        sy = ttk.Scrollbar(inner, orient=tk.VERTICAL)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        sx = ttk.Scrollbar(inner, orient=tk.HORIZONTAL)
        sx.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tree = ttk.Treeview(inner, columns=cols, show='tree headings', yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.tree.heading('#0', text='')
        self.tree.column('#0', width=34, minwidth=34, stretch=False, anchor=tk.CENTER)   # the signal marker
        for c in cols:
            anchor = tk.W if c in text_cols else tk.E
            self.tree.heading(c, text=c, anchor=anchor, command=lambda c=c: self.sort_tree(c))
            self.tree.column(c, width=col_widths.get(c, 100), anchor=anchor)
        self.tree.tag_configure('plain', background=T['card'])
        self.tree.tag_configure('zebra', background=T['zebra'])
        self.tree.tag_configure('tb', background=T['tint_b'])
        self.tree.tag_configure('ts', background=T['tint_s'])
        self.tree.tag_configure('error', background=T['err_bg'], foreground=T['err_fg'])
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        sy.config(command=self.tree.yview)
        sx.config(command=self.tree.xview)
        
        self.tree.bind('<Double-1>', self.show_details)
    
    def build_scrollable_tab(self, text):
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text=f"  {text}  ")
        
        canvas = tk.Canvas(tab, bg=T['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=T['bg'])
        
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._scroll_canvases.append(canvas)

        return frame

    def _on_mousewheel(self, e):
        """Scroll whichever scrollable tab canvas is under the mouse pointer."""
        try:
            w = self.root.winfo_containing(e.x_root, e.y_root) or getattr(e, 'widget', None)
        except (KeyError, tk.TclError):
            return  # pointer over an internal Tk widget (e.g. combobox dropdown)
        while isinstance(w, tk.Misc):
            if w in self._scroll_canvases:
                w.yview_scroll(int(-1 * (e.delta / 120)), "units")
                return
            w = w.master

    @staticmethod
    def _typing_in(widget):
        """True if keyboard focus is in a text-entry widget (so shortcuts like Delete shouldn't fire)."""
        return isinstance(widget, (tk.Entry, tk.Text, tk.Spinbox, ttk.Entry))

    @staticmethod
    def _wl_symbol(display):
        """Watchlist listbox rows look like 'SYMBOL  [Group1, Group2]' - return just the symbol."""
        return display.split('  ')[0].strip()
    
    def build_breakdown_tab(self):
        self.bd_frame = self.build_scrollable_tab("Score Breakdown")
        tk.Label(self.bd_frame, text="Double-click a stock in Scan Results to view breakdown",
                bg=THEME['bg'], fg=THEME['fg2'], font=(ui.FONT, 12)).pack(pady=60)
    
    def build_targets_tab(self):
        self.tg_frame = self.build_scrollable_tab("Stop-Loss & Targets")
        tk.Label(self.tg_frame, text="Double-click a stock in Scan Results to view targets",
                bg=THEME['bg'], fg=THEME['fg2'], font=(ui.FONT, 12)).pack(pady=60)
    
    def build_patterns_tab(self):
        self.pt_frame = self.build_scrollable_tab("Pattern Analysis")
        tk.Label(self.pt_frame, text="Double-click a stock in Scan Results to view detected patterns",
                bg=THEME['bg'], fg=THEME['fg2'], font=(ui.FONT, 12)).pack(pady=60)
    

    def build_corporate_tab(self):
        """Build Corporate Actions tab - comprehensive scanner with live NSE/BSE data."""
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Corporate Actions  ")

        # Header
        header = tk.Frame(tab, bg=T['bg2'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="Corporate actions (live from NSE and BSE)",
                 bg=T['bg2'], fg=T['fg'], font=(ui.DISPLAY, 14, 'bold')).pack(side=tk.LEFT, padx=16)

        self.btn(header, "Export CSV", T['success'], self.export_corporate_csv).pack(side=tk.RIGHT, padx=5)
        self.btn(header, "View Details", None, self.show_corporate_popup).pack(side=tk.RIGHT, padx=5)
        self.btn(header, "SCAN ALL", T['accent'], self.load_corporate_actions).pack(side=tk.RIGHT, padx=5)

        # Stats bar
        stats_bar = tk.Frame(tab, bg=T['bg3'], height=35)
        stats_bar.pack(fill=tk.X)
        stats_bar.pack_propagate(False)

        self.corp_stats_labels = {}
        for key, label, color in [('total', 'Total', T['accent']), ('upcoming', 'Upcoming', T['success']),
                                   ('dividends', 'Dividends', T['gold']), ('splits', 'Splits', T['warning']),
                                   ('bonus', 'Bonus', T['fg'])]:
            frame = tk.Frame(stats_bar, bg=T['bg3'])
            frame.pack(side=tk.LEFT, padx=15)
            tk.Label(frame, text=label, bg=T['bg3'], fg=T['fg3'], font=(ui.FONT, 8)).pack(side=tk.LEFT)
            lbl = tk.Label(frame, text="0", bg=T['bg3'], fg=color, font=(ui.FONT, 11, 'bold'))
            lbl.pack(side=tk.LEFT, padx=5)
            self.corp_stats_labels[key] = lbl

        self.corp_source_lbl = tk.Label(stats_bar, text="Source: -", bg=T['bg3'], fg=T['fg3'], font=(ui.FONT, 8))
        self.corp_source_lbl.pack(side=tk.RIGHT, padx=15)

        # Main content - PanedWindow
        content = tk.PanedWindow(tab, orient=tk.HORIZONTAL, bg=T['bg'])
        content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # LEFT - Stock list
        left = tk.LabelFrame(content, text=" Watchlist ", bg=T['bg'], fg=T['accent'], font=(ui.FONT, 10, 'bold'))
        content.add(left, width=220)

        self.corp_listbox = tk.Listbox(left, font=(ui.FONT, 11), width=22)
        self.corp_listbox.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self.corp_listbox.bind('<Double-1>', lambda e: self.show_corporate_popup())

        # RIGHT - Actions table
        right = tk.Frame(content, bg=T['bg'])
        content.add(right)

        # Filter bar
        filter_bar = tk.Frame(right, bg=T['bg2'])
        filter_bar.pack(fill=tk.X, pady=(0, 3))

        tk.Label(filter_bar, text="Show:", bg=T['bg2'], fg=T['fg'], font=(ui.FONT, 9)).pack(side=tk.LEFT, padx=5)
        self.corp_filter_var = tk.StringVar(value="All")
        for val in ["All", "Upcoming", "Past", "Dividends", "Splits", "Bonus", "Rights", "Buyback"]:
            tk.Radiobutton(filter_bar, text=val, variable=self.corp_filter_var, value=val,
                          bg=T['bg2'], fg=T['fg'], selectcolor=T['bg3'], font=(ui.FONT, 8),
                          command=self._filter_corporate_actions).pack(side=tk.LEFT, padx=2)

        # Actions Treeview
        tree_frame = tk.Frame(right, bg=T['bg'])
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ('Symbol', 'Company', 'Type', 'Action', 'Amount', 'Ex-Date', 'Record Date', 'Days', 'Status', 'Source')
        sy = ttk.Scrollbar(tree_frame)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        sx = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        sx.pack(side=tk.BOTTOM, fill=tk.X)

        self.corp_tree = ttk.Treeview(tree_frame, columns=cols, show='headings',
                                       yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.config(command=self.corp_tree.yview)
        sx.config(command=self.corp_tree.xview)

        widths = {'Symbol': 75, 'Company': 140, 'Type': 65, 'Action': 220, 'Amount': 75,
                  'Ex-Date': 85, 'Record Date': 85, 'Days': 50, 'Status': 75, 'Source': 65}
        for col in cols:
            self.corp_tree.heading(col, text=col, anchor=tk.CENTER)
            self.corp_tree.column(col, width=widths.get(col, 80), anchor=tk.CENTER)

        self.corp_tree.pack(fill=tk.BOTH, expand=True)
        self.corp_tree.bind('<Double-1>', lambda e: self.show_corporate_popup())

        # Tag colors
        self.corp_tree.tag_configure('upcoming', background=T['tint_b'], foreground=T['fg'])
        self.corp_tree.tag_configure('today', background=T['warn_bg'], foreground=T['warn_fg'])
        self.corp_tree.tag_configure('past', background=T['card'], foreground=T['fg3'])

        # Status bar
        self.corp_status = tk.Label(tab, text="Click 'SCAN ALL' to fetch live corporate actions from NSE & BSE",
                                   bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 10))
        self.corp_status.pack(side=tk.BOTTOM, pady=5, before=content)    # stays visible however tall the table is

        # Internal state
        self.corp_engine = None
        self.corporate_data = {}      # symbol -> engine data dict
        self._corp_symbol_map = {}    # listbox display -> symbol

    def load_corporate_actions(self):
        """Scan ALL watchlist stocks for corporate actions using the engine."""
        if not self.watchlist:
            messagebox.showwarning("Warning", "Watchlist is empty!")
            return
        if getattr(self, '_corp_busy', False):
            return   # already scanning - a second scan alongside would list every action twice
        self._corp_busy = True

        # Clear existing
        for item in self.corp_tree.get_children():
            self.corp_tree.delete(item)
        self.corp_listbox.delete(0, tk.END)
        self.corporate_data = {}
        self._corp_symbol_map = {}

        self.corp_status.configure(text="Scanning... Please wait...")
        self.root.update()

        def scan():
            try:
                if CORP_ENGINE_OK:
                    engine = CorporateActionsEngine()
                    self.corp_engine = engine

                    def progress(msg, pct):
                        self.root.after(0, lambda m=msg: self.corp_status.configure(text=m))

                    results = engine.scan_watchlist(self.watchlist, callback=progress)

                    total_actions = 0
                    total_upcoming = 0
                    div_count = 0
                    split_count = 0
                    bonus_count = 0

                    for symbol in sorted(results.keys()):
                        data = results[symbol]
                        company = data.get('company', symbol)
                        upcoming_count = data.get('upcoming_count', 0)
                        action_count = data.get('action_count', 0)
                        total_actions += action_count
                        total_upcoming += upcoming_count

                        # Store data
                        self.corporate_data[symbol] = data

                        # Add to listbox with clean display
                        display = f"{symbol}  [{upcoming_count} upcoming / {action_count} total]"
                        self._corp_symbol_map[display] = symbol
                        self.root.after(0, lambda d=display:
                            self.corp_listbox.insert(tk.END, d))

                        # Add actions to treeview
                        for action in data.get('all_actions', []):
                            cat = action.get('category', 'other')
                            if cat == 'dividend': div_count += 1
                            elif cat == 'split': split_count += 1
                            elif cat == 'bonus': bonus_count += 1

                            days = action.get('days_until')
                            is_upcoming = action.get('is_upcoming', True)

                            if days is not None:
                                if days < 0:
                                    status = f"{abs(days)}d ago"
                                    tag = 'past'
                                elif days == 0:
                                    status = "TODAY!"
                                    tag = 'today'
                                else:
                                    status = f"in {days}d"
                                    tag = 'upcoming'
                            else:
                                status = "Upcoming" if is_upcoming else "Past"
                                tag = 'upcoming' if is_upcoming else 'past'
                            if action.get('estimated'):
                                status = f"est. {status}"   # projected from past years, not announced

                            amount_str = f"Rs.{action.get('amount', 0):.2f}" if action.get('amount', 0) > 0 else "-"
                            icon = action.get('icon', '')

                            vals = (
                                symbol,
                                company[:28],
                                f"{icon} {cat.title()}",
                                action.get('purpose', '')[:50],
                                amount_str,
                                action.get('ex_date', ''),
                                action.get('record_date', ''),
                                str(days) if days is not None else '',
                                status,
                                action.get('source', ''),
                            )

                            self.root.after(0, lambda v=vals, t=tag:
                                self.corp_tree.insert('', tk.END, values=v, tags=(t,)))

                    # Update stats
                    stats = engine.get_stats()
                    sources = ', '.join(stats.get('sources_used', ['Local DB']))

                    self.root.after(0, lambda: self.corp_stats_labels['total'].configure(text=str(total_actions)))
                    self.root.after(0, lambda: self.corp_stats_labels['upcoming'].configure(text=str(total_upcoming)))
                    self.root.after(0, lambda: self.corp_stats_labels['dividends'].configure(text=str(div_count)))
                    self.root.after(0, lambda: self.corp_stats_labels['splits'].configure(text=str(split_count)))
                    self.root.after(0, lambda: self.corp_stats_labels['bonus'].configure(text=str(bonus_count)))
                    self.root.after(0, lambda: self.corp_source_lbl.configure(text=f"Source: {sources}"))

                    self.root.after(0, lambda: self.corp_status.configure(
                        text=f"Done! {len(results)} stocks | {total_actions} actions | {total_upcoming} upcoming"))

                elif CORPORATE_OK:
                    self._load_corporate_fallback()
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error",
                        "No corporate actions module found!\nMake sure corporate_actions_engine.py exists."))

            except Exception as e:
                logger.error(f"Corporate scan error: {e}")
                self.root.after(0, lambda err=e: self.corp_status.configure(text=f"Error: {err}"))
                import traceback
                traceback.print_exc()
            finally:
                self._corp_busy = False

        threading.Thread(target=scan, daemon=True).start()

    def _load_corporate_fallback(self):
        """Fallback: use old corporate_actions module."""
        ca = CorporateActions()
        total = len(self.watchlist)

        for i, symbol in enumerate(sorted(self.watchlist)):
            try:
                self.root.after(0, lambda idx=i, s=symbol:
                    self.corp_status.configure(text=f"Loading {s} ({idx+1}/{total})..."))

                actions = ca.get_actions(symbol, 'NSE')
                self.corporate_data[symbol] = actions

                name = actions.get('name', symbol)[:25]
                upcoming = actions.get('upcoming_events', [])
                divs = actions.get('dividends', [])
                splits = actions.get('splits', [])

                # Convert to unified format for popup
                actions['_all_actions_list'] = []
                for ev in upcoming:
                    actions['_all_actions_list'].append({
                        'symbol': symbol, 'company': name, 'category': 'dividend',
                        'purpose': f"{ev.get('type', 'Dividend')} - {ev.get('details', '')}",
                        'amount': ev.get('amount', 0), 'ex_date': ev.get('date', ''),
                        'record_date': '', 'days_until': ev.get('days_until'),
                        'is_upcoming': True, 'is_past': False,
                        'source': 'Estimate' if ev.get('estimated') else 'Local DB',
                        'icon': 'Div', 'estimated': bool(ev.get('estimated')),
                    })
                for div in divs[:5]:
                    if not any(a['ex_date'] == div['date'] for a in actions['_all_actions_list']):
                        actions['_all_actions_list'].append({
                            'symbol': symbol, 'company': name, 'category': 'dividend',
                            'purpose': f"Historical Dividend - Rs.{div.get('amount', 0):.2f}",
                            'amount': div.get('amount', 0), 'ex_date': div.get('date', ''),
                            'record_date': '', 'days_until': None,
                            'is_upcoming': False, 'is_past': True, 'source': 'Local DB',
                            'icon': 'Div',
                        })
                for sp in splits:
                    actions['_all_actions_list'].append({
                        'symbol': symbol, 'company': name, 'category': 'split',
                        'purpose': f"Stock Split - {sp.get('ratio', 'N/A')}",
                        'amount': 0, 'ex_date': sp.get('date', ''),
                        'record_date': '', 'days_until': None,
                        'is_upcoming': False, 'is_past': True, 'source': 'Local DB',
                        'icon': 'Split',
                    })

                display = f"{symbol}  [{len(upcoming)} upcoming / {len(actions['_all_actions_list'])} total]"
                self._corp_symbol_map[display] = symbol
                self.root.after(0, lambda d=display: self.corp_listbox.insert(tk.END, d))

                for act in actions.get('_all_actions_list', []):
                    days = act.get('days_until')
                    if days is not None:
                        tag = 'upcoming' if days >= 0 else 'past'
                        status = f"in {days}d" if days > 0 else ("TODAY!" if days == 0 else f"{abs(days)}d ago")
                    else:
                        tag = 'past'
                        status = 'Past'
                    if act.get('estimated'):
                        status = f"est. {status}"

                    amount_str = f"Rs.{act.get('amount', 0):.2f}" if act.get('amount', 0) > 0 else "-"
                    vals = (symbol, name[:28], act.get('category', '').title(),
                            act.get('purpose', '')[:50], amount_str,
                            act.get('ex_date', ''), '', str(days) if days is not None else '', status, 'Local')
                    self.root.after(0, lambda v=vals, t=tag:
                        self.corp_tree.insert('', tk.END, values=v, tags=(t,)))

            except Exception as e:
                logger.error(f"Fallback error {symbol}: {e}")

        self.root.after(0, lambda: self.corp_status.configure(
            text=f"Loaded {len(self.corporate_data)} stocks (local data)"))

    def show_corporate_popup(self):
        """Show detailed corporate actions in popup - FIXED to work with engine data."""
        # Get selected symbol
        symbol = None

        # Try listbox first
        sel = self.corp_listbox.curselection()
        if sel:
            display = self.corp_listbox.get(sel[0])
            symbol = self._corp_symbol_map.get(display, display.split('  ')[0].strip())

        # Try treeview
        if not symbol:
            tree_sel = self.corp_tree.selection()
            if tree_sel:
                vals = self.corp_tree.item(tree_sel[0])['values']
                if vals:
                    symbol = str(vals[0]).strip()

        if not symbol:
            messagebox.showinfo("Info", "Select a stock first!\n\nClick a stock in the list on the left,\nor double-click a row in the table.")
            return

        # Look up data
        data = self.corporate_data.get(symbol)
        if not data:
            messagebox.showinfo("Info", f"No data for {symbol}.\nClick 'SCAN ALL' first.")
            return

        T = THEME

        # Create popup
        popup = tk.Toplevel(self.root)
        popup.title(f"Corporate Actions - {symbol}")
        popup.geometry("900x650")
        popup.configure(bg=T['bg'])
        ui.set_titlebar(popup, T['mode'] == 'dark')

        # Header
        hdr = tk.Frame(popup, bg=T['bg2'], height=55)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        company_name = data.get('company', data.get('name', symbol))
        tk.Label(hdr, text=f"{symbol}  -  {company_name}",
                bg=T['bg2'], fg=T['gold'], font=(ui.FONT, 16, 'bold')).pack(side=tk.LEFT, padx=15)

        # Content - scrollable text
        content = tk.Frame(popup, bg=T['bg'])
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_scroll = ttk.Scrollbar(content)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        text = tk.Text(content, bg=T['card'], fg=T['fg'], font=(ui.MONO, 11), relief=tk.FLAT,
                       highlightthickness=1, highlightbackground=T['line'], wrap=tk.WORD, yscrollcommand=text_scroll.set, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text_scroll.config(command=text.yview)

        # Build report
        lines = []
        lines.append("=" * 70)
        lines.append(f"  CORPORATE ACTIONS REPORT: {symbol}")
        lines.append(f"  Company: {company_name}")
        lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        sources = data.get('sources', ['N/A'])
        lines.append(f"  Sources: {', '.join(sources)}")
        lines.append("=" * 70)
        lines.append("")

        # --- Get actions - handle both engine format and fallback format ---
        all_actions = data.get('all_actions', [])
        if not all_actions and '_all_actions_list' in data:
            all_actions = data['_all_actions_list']

        upcoming = [a for a in all_actions if a.get('is_upcoming', True) and (a.get('days_until') is None or a.get('days_until', 0) >= 0)]
        past = [a for a in all_actions if not a.get('is_upcoming', True) or (a.get('days_until') is not None and a.get('days_until', 0) < 0)]

        # Sort upcoming by days_until ascending
        upcoming.sort(key=lambda x: x.get('days_until') if x.get('days_until') is not None else 9999)
        past.sort(key=lambda x: x.get('ex_date', ''), reverse=True)

        # Also check old-format upcoming_events
        old_upcoming = data.get('upcoming_events', [])
        if old_upcoming and not upcoming:
            for ev in old_upcoming:
                lines.append(f"  UPCOMING EVENT:")
                lines.append(f"  Date: {ev.get('date', 'N/A')} ({ev.get('days_until', '?')} days)")
                lines.append(f"  Type: {ev.get('type', '')}")
                lines.append(f"  Details: {ev.get('details', '')}")
                lines.append("")

        # === UPCOMING ACTIONS ===
        if upcoming:
            lines.append(f"  UPCOMING CORPORATE ACTIONS ({len(upcoming)}):")
            lines.append(f"  {'-'*60}")
            for act in upcoming:
                icon = act.get('icon', '')
                cat = act.get('category', 'other').upper()
                purpose = act.get('purpose', 'N/A')
                ex_date = act.get('ex_date', 'N/A')
                record_date = act.get('record_date', '')
                days = act.get('days_until')
                amount = act.get('amount', 0)
                source = act.get('source', '')

                days_str = f" ({days} days)" if days is not None else ""
                amount_str = f" | Rs.{amount:.2f}" if amount > 0 else ""

                lines.append(f"")
                lines.append(f"  [{cat}] {purpose}")
                if act.get('estimated'):
                    lines.append("    ** ESTIMATE projected from previous years' dates - NOT an announced dividend **")
                lines.append(f"    Ex-Date:      {ex_date}{days_str}")
                if record_date:
                    lines.append(f"    Record Date:  {record_date}")
                if amount > 0:
                    lines.append(f"    Amount:       Rs.{amount:.2f} per share")
                lines.append(f"    Source:       {source}")
        else:
            lines.append(f"  UPCOMING CORPORATE ACTIONS:")
            lines.append(f"  {'-'*60}")
            lines.append(f"  No upcoming corporate actions found for {symbol}")
        lines.append("")

        # === DIVIDEND HISTORY ===
        divs = data.get('dividends', [])
        # Also extract from past actions
        past_divs = [a for a in past if a.get('category') == 'dividend']
        if past_divs and not divs:
            divs = [{'date': a.get('ex_date', ''), 'amount': a.get('amount', 0)} for a in past_divs]

        lines.append(f"  DIVIDEND HISTORY ({len(divs)} records):")
        lines.append(f"  {'-'*60}")
        if divs:
            for div in divs[:15]:
                lines.append(f"    {div.get('date', 'N/A'):12s}  |  Rs.{div.get('amount', 0):>10.2f}")
        else:
            lines.append(f"  No dividend history available")
        lines.append("")

        # === DIVIDEND INFO ===
        div_yield = data.get('dividend_yield', 0)
        if isinstance(div_yield, (int, float)) and div_yield > 0:
            if div_yield < 1:  # stored as decimal
                div_yield *= 100
            lines.append(f"  DIVIDEND INFORMATION:")
            lines.append(f"  {'-'*60}")
            lines.append(f"    Yield:       {div_yield:.2f}%")
            div_rate = data.get('dividend_rate', 0)
            if div_rate:
                lines.append(f"    Annual Rate: Rs.{div_rate:.2f}")
            ex_div = data.get('ex_dividend_date', '')
            if ex_div and ex_div != 'N/A':
                lines.append(f"    Ex-Date:     {ex_div}")
            lines.append("")

        # === STOCK SPLITS ===
        splits = data.get('splits', [])
        past_splits = [a for a in past if a.get('category') == 'split']
        if past_splits and not splits:
            splits = [{'date': a.get('ex_date', ''), 'ratio': a.get('purpose', 'N/A')} for a in past_splits]

        lines.append(f"  STOCK SPLITS ({len(splits)} records):")
        lines.append(f"  {'-'*60}")
        if splits:
            for sp in splits[:10]:
                ratio = sp.get('ratio', 'N/A')
                lines.append(f"    {sp.get('date', 'N/A'):12s}  |  {ratio}")
        else:
            lines.append(f"  No stock splits found")
        lines.append("")

        # === BONUS ISSUES ===
        bonus = [a for a in all_actions if a.get('category') == 'bonus']
        if bonus:
            lines.append(f"  BONUS ISSUES ({len(bonus)} records):")
            lines.append(f"  {'-'*60}")
            for b in bonus:
                lines.append(f"    {b.get('ex_date', 'N/A'):12s}  |  {b.get('purpose', 'N/A')}")
            lines.append("")

        # === OTHER ACTIONS ===
        other_cats = ['rights', 'buyback', 'agm', 'merger']
        other_actions = [a for a in all_actions if a.get('category') in other_cats]
        if other_actions:
            lines.append(f"  OTHER CORPORATE ACTIONS ({len(other_actions)} records):")
            lines.append(f"  {'-'*60}")
            for oa in other_actions:
                cat = oa.get('category', '').upper()
                lines.append(f"    [{cat}] {oa.get('purpose', 'N/A')}")
                lines.append(f"      Ex-Date: {oa.get('ex_date', 'N/A')}")
            lines.append("")

        # === SUMMARY ===
        categories = {}
        for act in all_actions:
            cat = act.get('category', 'other')
            categories[cat] = categories.get(cat, 0) + 1

        if categories:
            lines.append(f"  SUMMARY:")
            lines.append(f"  {'-'*60}")
            for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
                icon = {'dividend': 'Div', 'split': 'Split', 'bonus': 'Bonus',
                        'rights': 'Rights', 'buyback': 'Buyback', 'agm': 'AGM',
                        'merger': 'Merger'}.get(cat, 'Other')
                lines.append(f"    {icon:10s}: {count} action(s)")
            lines.append(f"    {'Total':10s}: {len(all_actions)} action(s)")

        lines.append("")
        lines.append("=" * 70)
        lines.append("  DR. NILESH SHAH'S MARKET ANALYSIS | For educational purposes only")
        lines.append("=" * 70)

        text.insert(tk.END, '\n'.join(lines))
        text.config(state=tk.DISABLED)

        # Bottom buttons
        btn_frame = tk.Frame(popup, bg=T['bg'])
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        self.btn(btn_frame, "Close", T['bg3'], popup.destroy).pack(side=tk.RIGHT, padx=5)

        def copy_to_clipboard():
            popup.clipboard_clear()
            popup.clipboard_append('\n'.join(lines))
            messagebox.showinfo("Copied", "Report copied to clipboard!")

        self.btn(btn_frame, "Copy to Clipboard", T['accent'], copy_to_clipboard).pack(side=tk.RIGHT, padx=5)

    def _on_corp_stock_select(self, event):
        """When a stock is selected in the list, highlight its actions in the tree."""
        sel = self.corp_listbox.curselection()
        if not sel:
            return
        display = self.corp_listbox.get(sel[0])
        symbol = self._corp_symbol_map.get(display, display.split('  ')[0].strip())

        # Clear and re-select matching rows
        self.corp_tree.selection_remove(*self.corp_tree.get_children())
        for item in self.corp_tree.get_children():
            vals = self.corp_tree.item(item, 'values')
            if vals and str(vals[0]).strip() == symbol:
                self.corp_tree.selection_add(item)
                self.corp_tree.see(item)

    def _filter_corporate_actions(self):
        """Filter corporate actions treeview by category/type."""
        filter_val = self.corp_filter_var.get()

        for item in self.corp_tree.get_children():
            self.corp_tree.delete(item)

        for symbol, data in self.corporate_data.items():
            if not isinstance(data, dict):
                continue

            all_actions = data.get('all_actions', [])
            if not all_actions and '_all_actions_list' in data:
                all_actions = data['_all_actions_list']

            company = data.get('company', data.get('name', symbol))

            for action in all_actions:
                cat = action.get('category', 'other')
                is_upcoming = action.get('is_upcoming', True)

                # Apply filter
                if filter_val == "Upcoming" and not is_upcoming:
                    continue
                elif filter_val == "Past" and is_upcoming:
                    continue
                elif filter_val not in ("All", "Upcoming", "Past"):
                    if filter_val.lower() != cat:
                        continue

                days = action.get('days_until')
                if days is not None:
                    if days < 0:
                        status = f"{abs(days)}d ago"
                        tag = 'past'
                    elif days == 0:
                        status = "TODAY!"
                        tag = 'today'
                    else:
                        status = f"in {days}d"
                        tag = 'upcoming'
                else:
                    status = "Upcoming" if is_upcoming else "Past"
                    tag = 'upcoming' if is_upcoming else 'past'
                if action.get('estimated'):
                    status = f"est. {status}"

                amount_str = f"Rs.{action.get('amount', 0):.2f}" if action.get('amount', 0) > 0 else "-"
                icon = action.get('icon', '')

                vals = (
                    symbol,
                    company[:28],
                    f"{icon} {cat.title()}",
                    action.get('purpose', '')[:50],
                    amount_str,
                    action.get('ex_date', ''),
                    action.get('record_date', ''),
                    str(days) if days is not None else '',
                    status,
                    action.get('source', ''),
                )

                self.corp_tree.insert('', tk.END, values=vals, tags=(tag,))

    def export_corporate_csv(self):
        """Export corporate actions to CSV."""
        if not self.corporate_data:
            messagebox.showwarning("Warning", "No data! Click 'SCAN ALL' first.")
            return

        fp = filedialog.asksaveasfilename(defaultextension=".csv",
            initialfile=f"corporate_actions_{datetime.now().strftime('%Y%m%d')}.csv",
            filetypes=[("CSV", "*.csv")])
        if not fp:
            return

        try:
            with open(fp, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Symbol', 'Company', 'Category', 'Purpose', 'Amount',
                                'Ex-Date', 'Record Date', 'Days Until', 'Status', 'Source'])

                for symbol, data in self.corporate_data.items():
                    if not isinstance(data, dict):
                        continue
                    all_actions = data.get('all_actions', [])
                    if not all_actions and '_all_actions_list' in data:
                        all_actions = data['_all_actions_list']

                    for action in all_actions:
                        writer.writerow([
                            symbol,
                            action.get('company', data.get('company', '')),
                            action.get('category', ''),
                            action.get('purpose', ''),
                            action.get('amount', ''),
                            action.get('ex_date', ''),
                            action.get('record_date', ''),
                            action.get('days_until', ''),
                            'Upcoming' if action.get('is_upcoming') else 'Past',
                            action.get('source', ''),
                        ])

            messagebox.showinfo("Exported", f"Saved to {os.path.basename(fp)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))


    def build_charts_tab(self):
        """Build Charts tab: one stock's price chart, or the 3D market map of the whole scan."""
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Charts  ")
        self.charts_tab = tab

        header = tk.Frame(tab, bg=T['bg2'], height=54)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Frame(tab, bg=T['line'], height=1).pack(fill=tk.X)

        tk.Label(header, text="Stock charts", bg=T['bg2'], fg=T['fg'],
                 font=(ui.DISPLAY, 14, 'bold')).pack(side=tk.LEFT, padx=16)

        map_btn = self.btn(header, "3D market map", None, self.show_market_map)
        map_btn.pack(side=tk.RIGHT, padx=(6, 16))
        Tooltip(map_btn, "Every scanned stock in 3D: score, RSI and strength against the Nifty")
        self.btn(header, "Show chart", T['accent'], self.show_stock_chart).pack(side=tk.RIGHT, padx=6)

        self.chart_period_var = tk.StringVar(value="6mo")
        periods = tk.Frame(header, bg=T['bg2'])
        periods.pack(side=tk.RIGHT, padx=12)
        tk.Label(periods, text="Period", bg=T['bg2'], fg=T['fg2'], font=(ui.FONT, 10)).pack(side=tk.LEFT, padx=(0, 6))
        for label, val in [("1M", "1mo"), ("3M", "3mo"), ("6M", "6mo"), ("1Y", "1y"), ("2Y", "2y")]:
            tk.Radiobutton(periods, text=label, variable=self.chart_period_var, value=val, indicatoron=0,
                           bg=T['bg3'], fg=T['fg'], selectcolor=T['sel_bg'], activebackground=T['line'],
                           activeforeground=T['fg'], relief=tk.FLAT, bd=0, padx=10, pady=4, cursor='hand2',
                           font=(ui.FONT, 9, 'bold'), offrelief=tk.FLAT).pack(side=tk.LEFT, padx=1)

        self.chart_frame = tk.Frame(tab, bg=T['bg'])
        self.chart_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        self._chart_state = None

        if not MATPLOTLIB_OK:
            tk.Label(self.chart_frame, text="Install matplotlib for charts:\npip install matplotlib",
                     bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 14)).pack(pady=50)
        else:
            tk.Label(self.chart_frame, text="Pick a stock in Scan Results or the Watchlist, then click Show chart.\n"
                                            "The 3D market map shows every scanned stock at once.",
                     bg=T['bg'], fg=T['fg2'], font=(ui.FONT, 12), justify=tk.CENTER).pack(pady=60)

    def _clear_chart(self):
        for widget in self.chart_frame.winfo_children():
            widget.destroy()

    def show_stock_chart(self):
        """Show stock chart."""
        if not MATPLOTLIB_OK:
            messagebox.showerror("Error", "Install matplotlib: pip install matplotlib")
            return

        sel = self.tree.selection()
        if not sel:
            wl_sel = self.wl_list.curselection()
            if wl_sel:
                symbol = self._wl_symbol(self.wl_list.get(wl_sel[0]))
            else:
                messagebox.showinfo("Info", "Select a stock first!")
                return
        else:
            symbol = str(self.tree.item(sel[0])['values'][0])

        period = self.chart_period_var.get()
        self._clear_chart()

        loading = tk.Label(self.chart_frame, text=f"Loading {symbol}...",
                           bg=THEME['bg'], fg=THEME['fg2'], font=(ui.FONT, 12))
        loading.pack(pady=20)
        self.root.update()

        def fetch():
            # Network fetch in the background; all Tk work happens in render() on the main thread
            try:
                df = self.analyzer.fetch(symbol, period)
                self.gui.schedule(render, df)
            except Exception as e:
                self.gui.schedule(fail, str(e))

        def fail(msg):
            if loading.winfo_exists():
                loading.configure(text=msg, fg=THEME['danger2'])
            messagebox.showerror("Error", msg)

        def render(df):
            try:
                if df is None or df.empty:
                    fail(f"No data for {symbol}")
                    return
                if loading.winfo_exists():
                    loading.destroy()
                self._render_stock_chart(symbol, period, df)
            except Exception as e:
                fail(str(e))

        threading.Thread(target=fetch, daemon=True).start()

    def _render_stock_chart(self, symbol, period, df, animate=True):
        """Price with its 20- and 50-day averages over volume. The lines draw themselves in."""
        T = THEME
        self._clear_chart()
        self._chart_state = ('stock', symbol, period, df)
        fig = Figure(figsize=(14, 8), dpi=100, facecolor=T['card'], layout='constrained')
        gs = fig.add_gridspec(2, 1, height_ratios=(3, 1.3))

        ax1 = fig.add_subplot(gs[0])
        self._style_axes(ax1)
        # A new listing comes with 1-hour candles (its whole history, whatever the period).
        # They are drawn one after another, without gaps for the nights and weekends.
        hourly = MARKET_DATA_OK and market_data.is_hourly(df)
        x = np.arange(len(df)) if hourly else df.index
        close = df['Close']
        series = [(close, ax1.plot(x, close, color=T['series0'], linewidth=2, label='Close')[0])]
        if len(df) >= 20:
            sma = close.rolling(20).mean()
            series.append((sma, ax1.plot(x, sma, color=T['series1'], linewidth=1.2, label='SMA 20')[0]))
        if len(df) >= 50:
            sma = close.rolling(50).mean()
            series.append((sma, ax1.plot(x, sma, color=T['series2'], linewidth=1.2, label='SMA 50')[0]))
        floor = float(close.min()) * 0.98
        area = [ax1.fill_between(x, close, floor, color=T['series0'], alpha=0.12, linewidth=0)]

        ax1.set_title(f'{symbol} (new listing - 1-hour candles)' if hourly else f'{symbol} ({period})',
                      color=T['fg'], fontsize=13, loc='left', fontweight='bold')
        ax1.legend(fontsize=8, frameon=False, labelcolor=T['chart_fg'], loc='upper left')
        ax1.set_ylim(floor, float(close.max()) * 1.02)

        ax1.tick_params(labelbottom=False)
        ax2 = fig.add_subplot(gs[1], sharex=ax1)
        self._style_axes(ax2)
        ax2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: f"{v / 1e7:.1f} Cr" if v >= 1e7 else f"{v / 1e5:.0f} L" if v >= 1e5 else f"{v:,.0f}"))
        up = (df['Close'] >= df['Open']).tolist()
        ax2.bar(x, df['Volume'], color=[T['buy'] if u else T['sell'] for u in up], alpha=0.95)
        ax2.set_ylabel('Volume', color=T['chart_fg'])
        if hourly:   # label each day at its first candle
            starts = [i for i in range(len(df)) if i == 0 or df.index[i].date() != df.index[i - 1].date()]
            ax2.set_xticks(starts)
            ax2.set_xticklabels([df.index[i].strftime('%d %b') for i in starts])

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.configure(highlightthickness=1, highlightbackground=T['line'])
        widget.pack(fill=tk.BOTH, expand=True)

        if not animate or not ui.Motion.enabled or len(df) < 3:
            return
        ax1.set_xlim(ax1.get_xlim())

        def step(v):
            n = max(2, int(len(df) * v))
            for data, line in series:
                line.set_data(x[:n], data.iloc[:n])
            area[0].remove()
            area[0] = ax1.fill_between(x[:n], close.iloc[:n], floor, color=T['series0'], alpha=0.12, linewidth=0)
            canvas.draw()
        ui.tween(widget, 900, step, frame=30)

    def show_market_map(self):
        """3D market map: every scanned stock as a point - score up, RSI across, strength
        against the Nifty 50 (3 months) into the screen. It turns slowly until you click it;
        drag to turn it yourself."""
        if not MATPLOTLIB_OK:
            messagebox.showerror("Error", "Install matplotlib: pip install matplotlib")
            return
        results = [r for r in getattr(self, '_all_results', self.results) if r.get('score') is not None]
        if not results:
            messagebox.showinfo("Info", "Scan stocks first (F5) - the map shows the scan results.")
            return
        T = THEME
        self._clear_chart()
        self._chart_state = ('map',)
        self.nb.select(self.charts_tab)

        fig = Figure(figsize=(13, 7.6), dpi=100, facecolor=T['card'])
        ax = fig.add_subplot(111, projection='3d')
        ax.set_facecolor(T['card'])
        pane = matplotlib.colors.to_rgba(T['bg3'], 0.6)
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.set_pane_color(pane)
            axis.label.set_color(T['chart_fg'])
            try:
                axis._axinfo['grid'].update(color=T['chart_grid'], linewidth=0.6)
                axis.line.set_color(T['line'])
            except Exception:
                pass
        ax.tick_params(colors=T['chart_fg'], labelsize=8)

        def rs3(r):
            v = (r.get('rs') or {}).get('3M')
            return v if v is not None else 0.0
        markers = {'STRONG BUY': '^', 'BUY': '^', 'HOLD': 's', 'SELL': 'v', 'STRONG SELL': 'v'}
        for rec, label in (('STRONG BUY', 'Strong buy'), ('BUY', 'Buy'), ('HOLD', 'Hold'), ('SELL', 'Sell'), ('STRONG SELL', 'Strong sell')):
            pts = [r for r in results if r['rec'] == rec]
            if not pts:
                continue
            xs, ys, zs = [r['rsi'] for r in pts], [rs3(r) for r in pts], [r['score'] for r in pts]
            c = ui.signal_color(T, rec)
            for x, y, z in zip(xs, ys, zs):      # a thin stem down to the floor helps judge height
                ax.plot([x, x], [y, y], [0, z], color=c, linewidth=0.9, alpha=0.55)
            ax.scatter(xs, ys, zs, color=c, marker=markers[rec], s=80 if 'STRONG' in rec else 50,
                       edgecolors=T['card'], linewidths=0.8, depthshade=True, label=f"{label} ({len(pts)})")
        ranked = sorted(results, key=lambda r: r['score'])
        for r in ranked[-4:] + ranked[:2]:      # the best and the weakest, named
            ax.text(r['rsi'], rs3(r), r['score'] + 3, r['symbol'], fontsize=8, color=T['fg'], ha='center')
        ax.set_xlabel('RSI', labelpad=8)
        ax.set_ylabel('vs Nifty 50, 3 months (%)', labelpad=8)
        ax.set_zlabel('Score', labelpad=6)
        ax.set_xlim(0, 100)
        ax.set_zlim(0, 100)
        ax.set_box_aspect((1.5, 1.1, 0.9), zoom=1.15)
        fig.legend(loc='upper left', bbox_to_anchor=(0.012, 0.9), frameon=False, labelcolor=T['chart_fg'], fontsize=9)
        fig.text(0.015, 0.95, f"3D market map: {len(results)} stocks", color=T['fg'], fontsize=13, fontweight='bold', va='center')
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        widget = canvas.get_tk_widget()
        widget.configure(highlightthickness=1, highlightbackground=T['line'])
        widget.pack(fill=tk.BOTH, expand=True)
        tk.Label(self.chart_frame, text="Higher = better score. Right = higher RSI. Further back = beating the Nifty 50 over 3 months. "
                                        "The map turns by itself - click it to stop, drag to turn it.",
                 bg=T['bg'], fg=T['fg2'], font=(ui.FONT, 9)).pack(anchor=tk.W, pady=(6, 0))

        state = {'elev': 8, 'azim': -70, 'stop': False}
        ax.view_init(elev=state['elev'], azim=state['azim'])
        canvas.draw()
        canvas.mpl_connect('button_press_event', lambda e: state.update(stop=True))

        def fly_in(v):      # the camera rises over the map once...
            state['elev'] = 8 + 16 * v
            ax.view_init(elev=state['elev'], azim=state['azim'])
            canvas.draw()
        ui.tween(widget, 1200, fly_in, done=lambda: self._spin_map(canvas, ax, state), ease=ui.ease_in_out, frame=30)

    def _spin_map(self, canvas, ax, state):
        """...then turns slowly while the Charts tab is open, until the map is clicked."""
        widget = canvas.get_tk_widget()
        try:
            if state['stop'] or not widget.winfo_exists() or not ui.Motion.enabled:
                return
            if self.nb.select() == str(self.charts_tab):
                state['azim'] += 0.8
                ax.view_init(elev=state['elev'], azim=state['azim'])
                canvas.draw()       # draw now, then wait: the next turn is queued only after this frame is done
            widget.after(60, lambda: self._spin_map(canvas, ax, state))
        except tk.TclError:
            pass

    def build_sector_tab(self):
        """Build Sector Analysis tab."""
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Sector  ")

        header = tk.Frame(tab, bg=T['bg2'], height=54)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Frame(tab, bg=T['line'], height=1).pack(fill=tk.X)

        tk.Label(header, text="Sector analysis", bg=T['bg2'], fg=T['fg'],
                 font=(ui.DISPLAY, 14, 'bold')).pack(side=tk.LEFT, padx=16)
        self.btn(header, "Analyze", T['accent'], self.analyze_sectors).pack(side=tk.RIGHT, padx=16)

        cols = ('Sector', 'Stocks', 'Avg Score', 'Chg', 'Buy', 'Hold', 'Sell', 'Best', 'Rotation', 'Rank')
        body = tk.Frame(tab, bg=T['bg'])
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        left = tk.Frame(body, bg=T['bg'])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.sector_3d_frame = tk.Frame(body, bg=T['bg'], width=560)
        self.sector_3d_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        self.sector_3d_frame.pack_propagate(False)
        self.sector_tree = ttk.Treeview(left, columns=cols, show='headings', height=12)

        widths = {'Sector': 170, 'Stocks': 60, 'Avg Score': 80, 'Chg': 70, 'Buy': 50, 'Hold': 50,
                  'Sell': 50, 'Best': 90, 'Rotation': 110, 'Rank': 50}
        for col in cols:
            self.sector_tree.heading(col, text=col, anchor=tk.CENTER)
            self.sector_tree.column(col, width=widths.get(col, 90), anchor=tk.CENTER)

        self.sector_status = tk.Label(left, text="Click 'Analyze' after scanning stocks", bg=T['bg'], fg=T['fg3'],
                                      font=(ui.FONT, 10), wraplength=760, justify=tk.LEFT)
        self.sector_status.pack(side=tk.BOTTOM, anchor=tk.W, pady=(8, 0))
        self.sector_tree.pack(fill=tk.BOTH, expand=True)
        tk.Label(self.sector_3d_frame, text="After Analyze, a 3D chart here shows how many stocks in each\n"
                                            "sector are buy, hold and sell.", bg=T['bg'], fg=T['fg3'],
                 font=(ui.FONT, 10), justify=tk.LEFT).pack(anchor=tk.W, pady=40, padx=8)
        self._sector_last = None

    def _draw_sector_3d(self, sector_scores):
        """3D bars: for each sector, how many of its stocks are buy, hold and sell. The bars
        grow up from the floor and the camera swings round once."""
        if not MATPLOTLIB_OK or not sector_scores:
            return
        T = THEME
        for w in self.sector_3d_frame.winfo_children():
            w.destroy()
        rows = sector_scores[:10]
        counts = []
        for i, (sector, avg, stocks) in enumerate(rows):
            buy = sum(1 for s in stocks if s['rec'] in ('STRONG BUY', 'BUY'))
            hold = sum(1 for s in stocks if s['rec'] == 'HOLD')
            sell = sum(1 for s in stocks if s['rec'] in ('SELL', 'STRONG SELL'))
            counts += [(i, 0, buy, T['buy']), (i, 1, hold, T['hold']), (i, 2, sell, T['sell'])]
        top = max([c for _, _, c, _ in counts] + [1])

        fig = Figure(figsize=(5.6, 5), dpi=100, facecolor=T['card'])
        ax = fig.add_subplot(111, projection='3d')
        ax.set_facecolor(T['card'])
        pane = matplotlib.colors.to_rgba(T['bg3'], 0.6)
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.set_pane_color(pane)
            try:
                axis._axinfo['grid'].update(color=T['chart_grid'], linewidth=0.6)
                axis.line.set_color(T['line'])
            except Exception:
                pass
        ax.tick_params(colors=T['chart_fg'], labelsize=7)
        ax.set_xticks([i + 0.3 for i in range(len(rows))])
        ax.set_xticklabels([f"#{i + 1}" for i in range(len(rows))])     # the table's Rank column
        ax.set_yticks([0.3, 1.3, 2.3])
        ax.set_yticklabels(['Buy', 'Hold', 'Sell'])
        ax.set_zlabel('Stocks', color=T['chart_fg'], fontsize=8)
        ax.set_xlim(-0.4, len(rows))
        ax.set_ylim(-0.4, 3)
        ax.set_zlim(0, top * 1.1)
        ax.zaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        ax.set_xlabel('Sector rank', color=T['chart_fg'], fontsize=8)
        ax.set_box_aspect((1.6, 1, 0.8), zoom=1.1)
        fig.text(0.03, 0.96, "Stocks per sector: buy, hold, sell", color=T['fg'], fontsize=11, fontweight='bold', va='center')
        fig.text(0.03, 0.915, "Bars follow the table's Rank column (#1 = strongest)", color=T['chart_fg'], fontsize=8, va='center')
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        bars = []

        def draw_bars(v):
            for b in bars:
                b.remove()
            bars.clear()
            for x, y, c, col in counts:
                if c:
                    bars.append(ax.bar3d(x, y, 0, 0.6, 0.6, max(c * v, 0.001), color=col, shade=True,
                                         edgecolor=T['card'], linewidth=0.3))

        canvas = FigureCanvasTkAgg(fig, master=self.sector_3d_frame)
        widget = canvas.get_tk_widget()
        widget.configure(highlightthickness=1, highlightbackground=T['line'])
        widget.pack(fill=tk.BOTH, expand=True)
        ax.view_init(elev=24, azim=-80)
        draw_bars(0 if ui.Motion.enabled else 1)
        canvas.draw()

        def step(v):
            draw_bars(v)
            ax.view_init(elev=24, azim=-80 + 22 * v)
            canvas.draw()
        ui.tween(widget, 1300, step, ease=ui.ease_in_out, frame=30)

    def analyze_sectors(self):
        """Analyze sectors with rotation signals."""
        if not self.results:
            messagebox.showinfo("Info", "Scan stocks first!")
            return
        if getattr(self, '_sector_busy', False):
            return
        results = list(self.results)
        self._sector_busy = True
        self.sector_status.configure(text="Looking up sectors (first time only - cached afterwards)...")
        
        def work():
            sectors = {}
            if MARKET_DATA_OK:
                try:
                    sectors = market_data.get_sectors([r['symbol'] for r in results])
                except Exception as e:
                    logger.error(f"Sector lookup failed: {e}")
            # Each stock's score from about a week ago (or, while the score history is shorter
            # than that, from its previous scan day) - to see which sectors are rising or falling
            earlier = {}
            if HISTORY_OK:
                try:
                    symbols = [r['symbol'] for r in results]
                    week_ago = (datetime.now() - timedelta(days=ROTATION_DAYS - 1)).strftime('%Y-%m-%d')
                    earlier = score_history.previous(symbols, before_day=week_ago)
                    for symbol, row in score_history.previous(symbols).items():
                        earlier.setdefault(symbol, row)
                except Exception as e:
                    logger.error(f"Score history read failed: {e}")
            self.gui.schedule(self._show_sectors, results, sectors, earlier)
        threading.Thread(target=work, daemon=True).start()

    def _show_sectors(self, results, yahoo_sectors, earlier=None):
        """Fill the Sector tab. Sector = Yahoo Finance's sector; if Yahoo has none, the built-in
        list; otherwise 'Other'. (The built-in list alone only knew ~90 large caps.)
        `earlier`: {symbol: score-history row} to measure each sector's change against."""
        earlier = earlier or {}
        self._sector_busy = False
        for item in self.sector_tree.get_children():
            self.sector_tree.delete(item)
        
        builtin = {s: sector for sector, stocks in SECTOR_MAP.items() for s in stocks}
        sector_data = {}
        for r in results:
            sector = yahoo_sectors.get(r['symbol']) or builtin.get(r['symbol']) or 'Other'
            sector_data.setdefault(sector, []).append(r)
        
        sector_scores = []
        for sector, stocks in sector_data.items():
            n = len(stocks)
            avg = sum(s['score'] for s in stocks) / n
            sector_scores.append((sector, avg, stocks))
        sector_scores.sort(key=lambda x: x[1], reverse=True)
        
        spread = sector_scores[0][1] - sector_scores[-1][1] if len(sector_scores) >= 2 else 0
        benchmark = sum(r['score'] for r in results) / len(results)   # the whole watchlist's average
        since = set()

        for rank, (sector, avg, stocks) in enumerate(sector_scores):
            n = len(stocks)
            buy = sum(1 for s in stocks if s['rec'] in ['STRONG BUY', 'BUY'])
            hold = sum(1 for s in stocks if s['rec'] == 'HOLD')
            sell = sum(1 for s in stocks if s['rec'] in ['SELL', 'STRONG SELL'])
            srt = sorted(stocks, key=lambda x: x['score'], reverse=True)

            # Change: the same stocks' scores now against their earlier scan
            moves = []
            for s in stocks:
                row = earlier.get(s['symbol'])
                if row and safe_float(row.get('score'), None) is not None:
                    moves.append(s['score'] - safe_float(row['score']))
                    since.add(row['date'])
            change = sum(moves) / len(moves) if moves else None

            self.sector_tree.insert('', tk.END, values=(
                sector, n, f"{avg:.1f}", "n/a" if change is None else f"{change:+.1f}", buy, hold, sell,
                srt[0]['symbol'] if srt else 'N/A',
                sector_rotation(avg, change, benchmark), f"#{rank+1}"
            ))

        self._sector_last = (results, yahoo_sectors, earlier)
        self._draw_sector_3d(sector_scores)
        if sector_scores:
            if since:
                when = min(since) if len(since) == 1 else f"{min(since)} to {max(since)}"
                compared = f"Chg = change in average score since the scan of {when}"
            else:
                compared = "Chg needs a scan from an earlier day - until then, rotation shows strength only"
            self.sector_status.configure(
                text=f"Strongest: {sector_scores[0][0]} ({sector_scores[0][1]:.1f}) | "
                     f"Weakest: {sector_scores[-1][0]} ({sector_scores[-1][1]:.1f}) | Spread: {spread:.1f} pts | "
                     f"Watchlist average: {benchmark:.1f} | {compared}")
        else:
            self.sector_status.configure(text="No sector information found for the scanned stocks.")
    
    def build_backtest_tab(self):
        """Build Backtest tab: does the score actually predict returns on these stocks?"""
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Backtest  ")

        header = tk.Frame(tab, bg=T['bg2'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Strategy backtest", bg=T['bg2'], fg=T['fg'],
                 font=(ui.DISPLAY, 14, 'bold')).pack(side=tk.LEFT, padx=16)

        self.bt_apply_btn = self.btn(header, "Apply Suggested Weights", T['success'], self.apply_suggested_weights)
        self.bt_apply_btn.pack(side=tk.RIGHT, padx=10)
        self.bt_apply_btn.configure(state=tk.DISABLED)
        self.bt_run_btn = self.btn(header, "Run Backtest", T['accent'], self.run_backtest)
        self.bt_run_btn.pack(side=tk.RIGHT, padx=5)

        self.bt_horizon_var = tk.StringVar(value="10 days")
        ttk.Combobox(header, textvariable=self.bt_horizon_var, values=["5 days", "10 days", "20 days"],
                     state='readonly', width=8).pack(side=tk.RIGHT, padx=5)
        tk.Label(header, text="Hold for:", bg=T['bg2'], fg=T['fg'], font=(ui.FONT, 10)).pack(side=tk.RIGHT)
        self.bt_history_var = tk.StringVar(value="5 years")
        ttk.Combobox(header, textvariable=self.bt_history_var, values=["2 years", "3 years", "5 years"],
                     state='readonly', width=8).pack(side=tk.RIGHT, padx=(5, 15))
        tk.Label(header, text="History:", bg=T['bg2'], fg=T['fg'], font=(ui.FONT, 10)).pack(side=tk.RIGHT)
        self.bt_liquid_var = tk.BooleanVar(value=False)
        self.bt_liquid_cb = tk.Checkbutton(header, variable=self.bt_liquid_var,
                                           text=f"Liquid stocks only (>= Rs {self.min_liquidity_cr:g} Cr/day)",
                                           bg=T['bg2'], fg=T['fg'], selectcolor=T['bg3'], activebackground=T['bg2'],
                                           font=(ui.FONT, 9))
        self.bt_liquid_cb.pack(side=tk.RIGHT, padx=10)

        weights_row = tk.Frame(tab, bg=T['bg'])
        weights_row.pack(fill=tk.X, padx=10, pady=(8, 0))
        self.btn(weights_row, "Re-check Weights", T['bg3'], self.recheck_weights).pack(side=tk.RIGHT, padx=5)
        self.bt_weights_lbl = tk.Label(weights_row, text="", bg=T['bg'], fg=T['fg'], font=(ui.FONT, 10, 'bold'),
                                       wraplength=1150, justify=tk.LEFT)
        self.bt_weights_lbl.pack(side=tk.LEFT, anchor=tk.W, padx=5)

        self.bt_status = tk.Label(tab, text="Tests the scoring system on your watchlist's past prices: for every past day it "
                                            "scores each stock exactly like a scan would, then checks what the price did next.",
                                  bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 10), wraplength=1300, justify=tk.LEFT)
        self.bt_status.pack(anchor=tk.W, padx=15, pady=(8, 2))
        self.bt_summary = tk.Label(tab, text="", bg=T['bg'], fg=T['fg'], font=(ui.FONT, 11, 'bold'),
                                   wraplength=1300, justify=tk.LEFT)
        self.bt_summary.pack(anchor=tk.W, padx=15, pady=(2, 6))

        tables = tk.Frame(tab, bg=T['bg'])
        tables.pack(fill=tk.BOTH, expand=True, padx=10)

        # Left: performance by recommendation
        left = tk.LabelFrame(tables, text=" What happened after each signal (newer 40% of history) ", bg=T['bg'],
                             fg=T['accent'], font=(ui.FONT, 10, 'bold'))
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        cols = ('Weights', 'Signal', 'Times', 'Avg Return', 'Win Rate', 'vs Avg')
        self.bt_bucket_tree = ttk.Treeview(left, columns=cols, show='headings', height=11)
        for c, w in zip(cols, (80, 100, 65, 85, 75, 75)):
            self.bt_bucket_tree.heading(c, text=c, anchor=tk.CENTER)
            self.bt_bucket_tree.column(c, width=w, anchor=tk.CENTER)
        self.bt_bucket_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.bt_bucket_tree.tag_configure('good', foreground=T['success'])
        self.bt_bucket_tree.tag_configure('bad', foreground=T['danger2'])

        # Right: each indicator's predictive power
        right = tk.LabelFrame(tables, text=" Which indicators actually help ", bg=T['bg'],
                              fg=T['accent'], font=(ui.FONT, 10, 'bold'))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        cols = ('Indicator', 'Current Wt', 'Power (older)', 'Power (newer)', 'Suggested Wt', 'Verdict')
        self.bt_ind_tree = ttk.Treeview(right, columns=cols, show='headings', height=11)
        for c, w in zip(cols, (105, 80, 95, 95, 90, 90)):
            self.bt_ind_tree.heading(c, text=c, anchor=tk.CENTER)
            self.bt_ind_tree.column(c, width=w, anchor=tk.CENTER)
        self.bt_ind_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.bt_ind_tree.tag_configure('good', foreground=T['success'])
        self.bt_ind_tree.tag_configure('bad', foreground=T['danger2'])

        tk.Label(tab, text="Power = rank correlation between the indicator's score and the next-period return "
                           "(above 0 = higher score was followed by better returns; 0.03+ is meaningful for daily stock data).  "
                           "Suggested weights are learned on the OLDER 60% of history and judged on the NEWER 40%, "
                           "so the comparison is honest. Past results don't guarantee future returns; daily signals overlap, "
                           "and delisted stocks aren't included.",
                 bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 8), wraplength=1300, justify=tk.LEFT).pack(side=tk.BOTTOM, anchor=tk.W, padx=15, pady=6, before=tables)

        self._bt_result = None
        self._bt_cache = None   # (key, samples, skipped) - reused when only the holding period changes
        self._update_weights_status()

    def run_backtest(self):
        if not BACKTEST_OK or not MARKET_DATA_OK:
            messagebox.showerror("Error", "backtest.py / market_data.py are missing.")
            return
        if not self.watchlist:
            messagebox.showwarning("Warning", "Add stocks to the watchlist first!")
            return
        watchlist = list(self.watchlist)
        years = int(self.bt_history_var.get().split()[0])
        horizon = int(self.bt_horizon_var.get().split()[0])
        weights = dict(Scorer.WEIGHTS)
        min_liq = self.min_liquidity_cr if self.bt_liquid_var.get() else 0
        key = (tuple(sorted(watchlist)), years)
        cached = self._bt_cache if self._bt_cache and self._bt_cache[0] == key else None

        self.bt_run_btn.configure(state=tk.DISABLED, text="RUNNING...")
        self.bt_apply_btn.configure(state=tk.DISABLED)
        self._bt_set_status(f"Loading {years} years of prices for {len(watchlist)} stocks...")

        def work():
            try:
                progress = lambda msg, pct=None: self.gui.schedule(self._bt_set_status, msg)
                if cached:
                    result = backtest.run_backtest(None, Scorer, weights, horizon, progress,
                                                   samples=cached[1], skipped=cached[2], min_liquidity_cr=min_liq)
                else:
                    data = market_data.load_history(watchlist, years=HISTORY_YEARS, progress=progress)
                    data = {s: market_data.slice_period(df, f"{years}y") for s, df in data.items()}
                    missing = [s for s in watchlist if s.upper() not in data]
                    result = backtest.run_backtest(data, Scorer, weights, horizon, progress, min_liquidity_cr=min_liq)
                    result['skipped'] = sorted(set(result.get('skipped', []) + missing))
                    if 'samples' in result:
                        self._bt_cache = (key, result['samples'], result['skipped'])
                result['years'] = years
                self.gui.schedule(self._show_backtest, result)
            except Exception as e:
                logger.error(f"Backtest error: {e}")
                self.gui.schedule(self._show_backtest, {'error': str(e)})

        threading.Thread(target=work, daemon=True).start()

    def _bt_set_status(self, msg):
        self.bt_status.configure(text=msg, fg=THEME['fg3'])

    def _show_backtest(self, r):
        self.bt_run_btn.configure(state=tk.NORMAL, text="Run Backtest")
        for tree in (self.bt_bucket_tree, self.bt_ind_tree):
            tree.delete(*tree.get_children())
        if r.get('error'):
            self.bt_status.configure(text=f"Backtest failed: {r['error']}", fg=THEME['danger'])
            self.bt_summary.configure(text="")
            return
        self._bt_result = r
        h = r['horizon']

        skipped = f"  |  Skipped (too little history): {', '.join(r['skipped'][:8])}" if r['skipped'] else ""
        if r.get('min_liquidity_cr'):
            skipped += (f"  |  Liquid only: {r['excluded_illiquid']:,} stock-days below "
                        f"Rs {r['min_liquidity_cr']:g} Cr/day excluded")
        ret_word = "vs. your watchlist's average" if r['relative'] else "(absolute)"
        self.bt_status.configure(
            text=f"{r['n_stocks']} stocks, {r['start']} to {r['end']}, {r['n_samples']:,} stock-days scored  |  "
                 f"Learned on {r['start']} to {r['split_date']}, tested on {r['split_date']} to {r['end']}  |  "
                 f"Holding {h} trading days (avg stock: {r['baseline_return']:+.2f}%, up {r['baseline_win']:.0f}% of the time)"
                 f"{skipped}", fg=THEME['fg3'])

        cur, sug = r['current'], r['suggested']
        def fmt(ev):
            return f"power {ev['ic']:+.3f}, best-scored 20% beat worst-scored 20% by {ev['spread']:+.2f}% per {h} days"
        lines = [f"Current weights: {fmt(cur)}"]
        color = THEME['fg']
        if sug:
            lines.append(f"Suggested weights: {fmt(sug)}")
            better_ic = sug['ic'] > cur['ic'] + 0.01
            better_spread = sug['spread'] > cur['spread'] + 0.05
            if better_ic and better_spread:
                lines.append("=> The suggested weights predicted better on unseen data. Consider 'Apply Suggested Weights'.")
                color = THEME['success']
            elif better_ic or better_spread:
                lines.append("=> Mixed result: the suggested weights "
                             + ("ranked stocks better overall, but the best-vs-worst gap was about the same."
                                if better_ic else "widened the best-vs-worst gap, but ranked stocks no better overall.")
                             + " Applying them is optional - the improvement is modest.")
            else:
                lines.append("=> The suggested weights were not better on unseen data - keep your current weights.")
            self.bt_apply_btn.configure(state=tk.NORMAL)
        else:
            lines.append("No indicator showed positive predictive power - no weights to suggest.")
        if cur['ic'] < 0:
            lines.append(f"Note: with the current weights, HIGHER scores were followed by slightly WORSE {h}-day returns ({ret_word}).")
            color = THEME['warning'] if color == THEME['fg'] else color
        self.bt_summary.configure(text="\n".join(lines), fg=color)

        def pct(v):
            return "-" if v is None else f"{v:+.2f}%"
        for label, ev in (("Current", cur), ("Suggested", sug)):
            if not ev:
                continue
            for b in ev['buckets']:
                tag = ()
                if b['vs_avg'] is not None and b['n'] >= 30:
                    good = b['vs_avg'] > 0 if 'BUY' in b['rec'] else b['vs_avg'] < 0 if 'SELL' in b['rec'] else None
                    tag = ('good',) if good else ('bad',) if good is False else ()
                self.bt_bucket_tree.insert('', tk.END, values=(
                    label, b['rec'], f"{b['n']:,}", pct(b['avg_return']),
                    "-" if b['win_rate'] is None else f"{b['win_rate']:.0f}%", pct(b['vs_avg'])), tags=tag)

        for c in r['components']:
            tr, te = c['ic_train'], c['ic_test']
            if tr == tr and te == te and tr > 0.01 and te > 0.01:
                verdict, tag = "Helps", ('good',)
            elif tr == tr and te == te and tr < -0.01 and te < -0.01:
                verdict, tag = "Hurts", ('bad',)
            else:
                verdict, tag = "Weak / mixed", ()
            self.bt_ind_tree.insert('', tk.END, values=(
                c['name'], c['weight'], f"{tr:+.3f}" if tr == tr else "-", f"{te:+.3f}" if te == te else "-",
                "-" if c['suggested'] is None else c['suggested'], verdict), tags=tag)

    def apply_suggested_weights(self):
        r = self._bt_result
        if not r or not r.get('suggested_weights'):
            return
        w = r['suggested_weights']
        names = backtest.COMPONENT_NAMES
        detail = "\n".join(f"  {names[k]:<14} {Scorer.WEIGHTS.get(k, 0):>3}  ->  {w[k]:>3}" for k in names)
        if not messagebox.askyesno("Apply Suggested Weights",
                f"Change scoring weights?\n\n{detail}\n\n"
                "You can restore the originals any time with Settings > Reset Defaults."):
            return
        today = datetime.now().strftime('%Y-%m-%d')
        self._set_weights(dict(w), {
            'source': 'backtest', 'applied': today, 'last_check': today,
            'horizon': r['horizon'], 'years': r.get('years', 5), 'liquid_only': bool(r.get('min_liquidity_cr')),
            'tested_power': {'suggested': round(r['suggested']['ic'], 4), 'previous': round(r['current']['ic'], 4)},
        })
        messagebox.showinfo("Applied", "Suggested weights applied and saved.\n\nRe-scan (F5) to see updated scores.\n\n"
                            f"The app re-checks them against the default weights every {self.WEIGHTS_RECHECK_DAYS} days "
                            "and tells you if the defaults start doing better.")
        self.run_backtest()   # refresh the table so 'Current Wt' shows the new weights

    def build_settings_tab(self):
        """Build Settings tab."""
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Settings  ")
        
        # Create scrollable frame
        canvas = tk.Canvas(tab, bg=T['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=T['bg'])
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._scroll_canvases.append(canvas)

        # Header
        header = tk.Frame(content, bg=T['bg2'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Settings", bg=T['bg2'], fg=T['fg'],
                 font=(ui.DISPLAY, 14, 'bold')).pack(side=tk.LEFT, padx=16)
        
        # ===== APPEARANCE =====
        look = tk.LabelFrame(content, text=" Appearance ", bg=T['bg'], fg=T['accent'], font=(ui.FONT, 11, 'bold'))
        look.pack(fill=tk.X, padx=20, pady=(14, 10))
        mode_row = tk.Frame(look, bg=T['bg'])
        mode_row.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(mode_row, text="Colours", bg=T['bg'], fg=T['fg'], font=(ui.FONT, 10), width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.light_btn = self.btn(mode_row, "Light", None, lambda: self.apply_appearance('light'),
                                  kind='primary' if T['mode'] == 'light' else 'secondary')
        self.light_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.dark_btn = self.btn(mode_row, "Dark", None, lambda: self.apply_appearance('dark'),
                                 kind='primary' if T['mode'] == 'dark' else 'secondary')
        self.dark_btn.pack(side=tk.LEFT, padx=4)
        tk.Label(mode_row, text="Light is the Daylight design; Dark is easier on the eyes at night.",
                 bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 9)).pack(side=tk.LEFT, padx=12)
        self.animations_var = tk.BooleanVar(value=ui.Motion.enabled)
        anim_row = tk.Frame(look, bg=T['bg'])
        anim_row.pack(fill=tk.X, padx=10, pady=(4, 10))
        tk.Label(anim_row, text="Motion", bg=T['bg'], fg=T['fg'], font=(ui.FONT, 10), width=18, anchor=tk.W).pack(side=tk.LEFT)
        tk.Checkbutton(anim_row, text="Animations (buttons, counters, charts that draw in, the turning 3D map)",
                       variable=self.animations_var, command=self.toggle_animations,
                       bg=T['bg'], fg=T['fg'], font=(ui.FONT, 10)).pack(side=tk.LEFT)
        if not ui.windows_allows_animation():
            tk.Label(look, text="Windows' own 'Animation effects' setting is off, so the app stays still too.",
                     bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 9)).pack(anchor=tk.W, padx=10, pady=(0, 8))

        # ===== EMAIL CONFIGURATION =====
        email_frame = tk.LabelFrame(content, text=" Email Report Configuration ", 
                                    bg=T['bg'], fg=T['accent'], font=(ui.FONT, 11, 'bold'))
        email_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.email_vars = {}
        email_fields = [
            ("SMTP Server:", "smtp_server", "smtp.gmail.com"),
            ("SMTP Port:", "smtp_port", "587"),
            ("Sender Email:", "sender_email", ""),
            ("App Password:", "sender_password", ""),
            ("Receiver Emails:", "receiver_emails", ""),
        ]
        
        for i, (label, key, default) in enumerate(email_fields):
            row = tk.Frame(email_frame, bg=T['bg'])
            row.pack(fill=tk.X, padx=10, pady=3)
            
            tk.Label(row, text=label, bg=T['bg'], fg=T['fg'],
                    font=(ui.FONT, 10), width=18, anchor=tk.W).pack(side=tk.LEFT)
            
            var = tk.StringVar(value=default)
            self.email_vars[key] = var
            
            show = '*' if 'password' in key.lower() else ''
            entry = tk.Entry(row, textvariable=var, bg=T['input'], fg=T['fg'],
                           font=(ui.FONT, 10), width=40, show=show,
                           relief=tk.FLAT, highlightbackground=T['border'], highlightthickness=1)
            entry.pack(side=tk.LEFT, padx=5)
            
            # Store password entry reference for toggle
            if key == 'sender_password':
                self.pw_entry = entry
                self.pw_visible = False
                self.btn(row, "Show", T['bg3'], self.toggle_password_visibility).pack(side=tk.LEFT, padx=2)
        
        # Load existing config into fields
        self._load_email_config_to_fields()
        
        email_btn_frame = tk.Frame(email_frame, bg=T['bg'])
        email_btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.btn(email_btn_frame, "Save Email Config", T['accent'], self.save_email_config).pack(side=tk.LEFT, padx=5)
        self.btn(email_btn_frame, "Test Email", None, self.test_email).pack(side=tk.LEFT, padx=5)
        self.btn(email_btn_frame, "Send Report Now", T['warning'], self.send_email_report).pack(side=tk.LEFT, padx=5)
        self.btn(email_btn_frame, "Clear Config", T['danger'], self.clear_email_config).pack(side=tk.LEFT, padx=5)
        
        # Email help text
        help_frame = tk.Frame(email_frame, bg=T['bg'])
        help_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(help_frame, text="Gmail setup guide:", bg=T['bg'], fg=T['gold'], font=(ui.FONT, 9, 'bold')).pack(anchor=tk.W)
        tk.Label(help_frame, text="1. Enable 2-Factor Authentication on your Google Account", bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 9)).pack(anchor=tk.W, padx=10)
        tk.Label(help_frame, text="2. Go to: https://myaccount.google.com/apppasswords", bg=T['bg'], fg=T['accent'], font=(ui.FONT, 9)).pack(anchor=tk.W, padx=10)
        tk.Label(help_frame, text="3. Generate App Password for 'Mail' → Use that 16-char password above", bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 9)).pack(anchor=tk.W, padx=10)
        tk.Label(help_frame, text="4. Port 587 = STARTTLS (recommended) | Port 465 = SSL", bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 9)).pack(anchor=tk.W, padx=10)
        
        # Email status indicator
        self.email_status_lbl = tk.Label(email_frame, text="", bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 9))
        self.email_status_lbl.pack(anchor=tk.W, padx=10, pady=5)
        self._update_email_status()
        
        # ===== AUTO REPORT SCHEDULING =====
        schedule_frame = tk.LabelFrame(content, text=" Auto Report Scheduling ", 
                                       bg=T['bg'], fg=T['accent'], font=(ui.FONT, 11, 'bold'))
        schedule_frame.pack(fill=tk.X, padx=20, pady=10)
        
        sched = self._load_schedule_config()
        self.auto_report_var = tk.BooleanVar(value=sched['enabled'])
        tk.Checkbutton(schedule_frame, text="Enable Auto-Report Email", 
                      variable=self.auto_report_var,
                      bg=T['bg'], fg=T['fg'], selectcolor=T['bg3'],
                      font=(ui.FONT, 10)).pack(anchor=tk.W, padx=10, pady=5)
        
        sched_row = tk.Frame(schedule_frame, bg=T['bg'])
        sched_row.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(sched_row, text="Send Time:", bg=T['bg'], fg=T['fg'],
                font=(ui.FONT, 10)).pack(side=tk.LEFT, padx=5)
        
        self.report_hour_var = tk.StringVar(value=str(sched['hour']))
        ttk.Combobox(sched_row, textvariable=self.report_hour_var,
                    values=[str(h) for h in range(24)], state='readonly', width=5).pack(side=tk.LEFT)
        tk.Label(sched_row, text=":", bg=T['bg'], fg=T['fg'], font=(ui.FONT, 10)).pack(side=tk.LEFT)
        
        self.report_min_var = tk.StringVar(value=f"{sched['minute']:02d}")
        ttk.Combobox(sched_row, textvariable=self.report_min_var,
                    values=[f"{m:02d}" for m in range(0, 60, 5)], state='readonly', width=5).pack(side=tk.LEFT)
        
        tk.Label(sched_row, text="(24-hour format)", bg=T['bg'], fg=T['fg3'],
                font=(ui.FONT, 9)).pack(side=tk.LEFT, padx=10)
        
        type_row = tk.Frame(schedule_frame, bg=T['bg'])
        type_row.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(type_row, text="Report Type:", bg=T['bg'], fg=T['fg'],
                font=(ui.FONT, 10)).pack(side=tk.LEFT, padx=5)
        
        self.report_type_var = tk.StringVar(value=sched['report_type'])
        ttk.Combobox(type_row, textvariable=self.report_type_var,
                    values=["Indian Only", "Indian + US", "US Only"], state='readonly', width=15).pack(side=tk.LEFT)
        
        sched_btns = tk.Frame(schedule_frame, bg=T['bg'])
        sched_btns.pack(fill=tk.X, padx=10, pady=(10, 2))
        self.btn(sched_btns, "Save Schedule", T['accent'], self.save_schedule).pack(side=tk.LEFT, padx=(0, 5))
        self.btn(sched_btns, "Install Windows Task", None, self.install_windows_task).pack(side=tk.LEFT, padx=5)
        self.btn(sched_btns, "Remove Windows Task", T['danger'], self.remove_windows_task).pack(side=tk.LEFT, padx=5)

        self.task_status_lbl = tk.Label(schedule_frame, text="Windows task: checking...", bg=T['bg'], fg=T['fg3'],
                                        font=(ui.FONT, 9))
        self.task_status_lbl.pack(anchor=tk.W, padx=10, pady=(2, 2))
        tk.Label(schedule_frame, text="The Windows task emails the report on NSE trading days even when this app is closed "
                                      "(weekends & NSE holidays are skipped; sent at most once a day).",
                 bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 8)).pack(anchor=tk.W, padx=10, pady=(0, 10))
        self.root.after(1500, self._update_task_status)
        
        # ===== LIQUIDITY =====
        liq_frame = tk.LabelFrame(content, text=" Liquidity Filter ",
                                  bg=T['bg'], fg=T['accent'], font=(ui.FONT, 11, 'bold'))
        liq_frame.pack(fill=tk.X, padx=20, pady=10)
        liq_row = tk.Frame(liq_frame, bg=T['bg'])
        liq_row.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(liq_row, text="Flag stocks trading less than Rs", bg=T['bg'], fg=T['fg'],
                 font=(ui.FONT, 10)).pack(side=tk.LEFT, padx=(5, 5))
        self.min_liquidity_var = tk.StringVar(value=f"{self.min_liquidity_cr:g}")
        tk.Spinbox(liq_row, from_=0, to=1000, increment=0.5, textvariable=self.min_liquidity_var, width=7,
                   bg=T['input'], fg=T['fg'], font=(ui.FONT, 10)).pack(side=tk.LEFT)
        tk.Label(liq_row, text="crore per day (average traded value, last 20 days)", bg=T['bg'], fg=T['fg'],
                 font=(ui.FONT, 10)).pack(side=tk.LEFT, padx=5)
        self.btn(liq_row, "Save", T['accent'], self.save_liquidity_setting).pack(side=tk.LEFT, padx=10)
        tk.Label(liq_frame, text="Thinly traded stocks can gap past a stop-loss and orders may not fill, so their "
                                 "targets are shown with a warning and they can be hidden in Scan Results.",
                 bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 8)).pack(anchor=tk.W, padx=15, pady=(0, 8))

        # ===== SCORING WEIGHTS =====
        weights_frame = tk.LabelFrame(content, text=" Scoring Weights (must total 100%) ", 
                                      bg=T['bg'], fg=T['accent'], font=(ui.FONT, 11, 'bold'))
        weights_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.weight_vars = {}
        weights = [('rsi', 'RSI', 12), ('macd', 'MACD', 12), ('ma', 'Moving Avg', 15),
                   ('boll', 'Bollinger', 8), ('stoch', 'Stochastic', 8), ('adx', 'ADX', 8),
                   ('vol', 'Volume', 8), ('mom', 'Momentum', 8), ('st', 'SuperTrend', 11),
                   ('vwap', 'VWAP', 10)]
        
        weights_grid = tk.Frame(weights_frame, bg=T['bg'])
        weights_grid.pack(fill=tk.X, padx=10, pady=10)
        
        for i, (key, name, default) in enumerate(weights):
            row_num = i // 2
            col_num = (i % 2) * 3

            tk.Label(weights_grid, text=f"{name}:", bg=T['bg'], fg=T['fg'],
                    font=(ui.FONT, 10), width=14, anchor=tk.W).grid(row=row_num, column=col_num, padx=5, pady=4, sticky='w')

            var = tk.IntVar(value=Scorer.WEIGHTS.get(key, default))   # saved weights, if any
            self.weight_vars[key] = var

            tk.Spinbox(weights_grid, from_=0, to=100, textvariable=var, width=5,
                      bg=T['input'], fg=T['fg'], font=(ui.FONT, 10)).grid(row=row_num, column=col_num+1, padx=5, pady=4)

        weight_btns = tk.Frame(weights_frame, bg=T['bg'])
        weight_btns.pack(fill=tk.X, padx=10, pady=10)
        self.btn(weight_btns, "Apply Weights", T['accent'], self.apply_weights).pack(side=tk.LEFT, padx=(0, 5))
        self.btn(weight_btns, "Reset Defaults", T['bg3'], self.reset_weights).pack(side=tk.LEFT, padx=5)
        tk.Label(weight_btns, text="Tip: the Backtest tab can suggest weights based on your stocks' history",
                 bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 9)).pack(side=tk.LEFT, padx=10)
        
        # ===== MODULE STATUS =====
        status_frame = tk.LabelFrame(content, text=" Module Status ", 
                                    bg=T['bg'], fg=T['accent'], font=(ui.FONT, 11, 'bold'))
        status_frame.pack(fill=tk.X, padx=20, pady=10)
        
        modules = [
            ("Pattern Recognition", PATTERN_OK),
            ("Daily Reports", REPORT_OK),
            ("Corporate Actions", True),
            ("Corp Actions Engine (NSE/BSE)", CORP_ENGINE_OK),
            ("Charts (matplotlib)", MATPLOTLIB_OK),
            ("PDF Export", REPORTLAB_OK),
            ("PDF Import", PDF_OK),
            ("PIL (Logo)", PIL_OK),
        ]
        
        for name, status in modules:
            color = T['success'] if status else T['danger']
            text = "ACTIVE" if status else "NOT INSTALLED"
            tk.Label(status_frame, text=f"{name}: {text}", bg=T['bg'], fg=color,
                    font=(ui.FONT, 10)).pack(anchor=tk.W, padx=20, pady=3)
    
    def save_email_config(self):
        """Save email configuration."""
        try:
            from daily_report import EmailConfig
            email_config = EmailConfig()
            
            smtp_server = self.email_vars['smtp_server'].get().strip()
            smtp_port_str = self.email_vars['smtp_port'].get().strip()
            sender_email = self.email_vars['sender_email'].get().strip()
            sender_password = self.email_vars['sender_password'].get().strip()
            receiver_str = self.email_vars['receiver_emails'].get().strip()
            receiver_emails = [e.strip() for e in receiver_str.split(',') if e.strip()]
            
            # Validate inputs
            if not smtp_server:
                messagebox.showwarning("Warning", "Please enter SMTP server!")
                return
            
            try:
                smtp_port = int(smtp_port_str) if smtp_port_str else 587
            except ValueError:
                messagebox.showwarning("Warning", "SMTP Port must be a number!")
                return
            
            if not sender_email:
                messagebox.showwarning("Warning", "Please enter sender email!")
                return
            
            if '@' not in sender_email:
                messagebox.showwarning("Warning", "Please enter a valid email address!")
                return
            
            if not sender_password:
                messagebox.showwarning("Warning", 
                    "Please enter App Password!\n\n"
                    "For Gmail:\n"
                    "1. Go to https://myaccount.google.com/apppasswords\n"
                    "2. Generate an App Password for 'Mail'\n"
                    "3. Use that 16-character password here")
                return
            
            if not receiver_emails:
                messagebox.showwarning("Warning", "Please enter at least one receiver email!")
                return
            
            # Validate receiver emails
            for email in receiver_emails:
                if '@' not in email:
                    messagebox.showwarning("Warning", f"Invalid receiver email: {email}")
                    return
            
            # Save configuration
            email_config.configure(
                smtp_server=smtp_server,
                smtp_port=smtp_port,
                sender_email=sender_email,
                sender_password=sender_password,
                receiver_emails=receiver_emails
            )
            
            # Verify it was saved correctly
            verify_config = EmailConfig()
            if verify_config.is_configured and verify_config.sender_password:
                messagebox.showinfo("Success", 
                    f"Email configuration saved and verified!\n\n"
                    f"From: {sender_email}\n"
                    f"To: {', '.join(receiver_emails)}\n"
                    f"Server: {smtp_server}:{smtp_port}\n"
                    f"Password: {'*' * len(sender_password)} (saved)\n\n"
                    f"Click 'Test Email' to verify it works.")
            else:
                messagebox.showwarning("Warning", 
                    "Config saved but verification failed.\n"
                    "Please try again.")
            
            # Update status indicator
            self._update_email_status()
                    
        except ImportError:
            messagebox.showerror("Error", "Daily report module not found!\nMake sure daily_report.py exists.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
            import traceback
            traceback.print_exc()
    
    def test_email(self):
        """Test email configuration."""
        if not REPORT_OK:
            messagebox.showerror("Error", "Daily report module not found.")
            return
        
        try:
            from daily_report import EmailConfig
            email_config = EmailConfig()
            
            if not email_config.is_configured:
                messagebox.showwarning("Warning", 
                    "Email not configured!\n\n"
                    "Steps:\n"
                    "1. Enter your email settings above\n"
                    "2. Click 'Save Email Config'\n"
                    "3. Then try 'Test Email' again.\n\n"
                    "For Gmail, you need an App Password:\n"
                    "https://myaccount.google.com/apppasswords")
                return
            
            if not email_config.sender_password:
                messagebox.showerror("Error", 
                    "Password is empty!\n\n"
                    "Please re-enter your email settings and click 'Save Email Config' again.\n\n"
                    "For Gmail, use App Password (not regular password):\n"
                    "https://myaccount.google.com/apppasswords")
                return
            
            self.status_lbl.configure(text="Testing email connection...")
            self.root.update()
            
            # First test connection
            if not email_config.test_connection():
                self.status_lbl.configure(text="Ready")
                messagebox.showerror("Connection Failed", 
                    f"Cannot connect or authenticate!\n\n"
                    f"Server: {email_config.smtp_server}:{email_config.smtp_port}\n"
                    f"From: {email_config.sender_email}\n\n"
                    f"Error: {email_config.last_error}")
                return
            
            # Now send test email
            try:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                
                msg = MIMEMultipart()
                msg['From'] = email_config.sender_email
                msg['To'] = ', '.join(email_config.receiver_emails)
                msg['Subject'] = "Test Email - DR. NILESH SHAH'S ANALYSIS"
                
                body = f"""
                <html>
                <body style="font-family: Arial, sans-serif; padding: 20px;">
                    <div style="background: linear-gradient(135deg, #1f6feb, #0d1b2a); color: white; padding: 20px; border-radius: 10px; text-align: center;">
                        <h1>DR. NILESH SHAH'S MARKET ANALYSIS</h1>
                        <h2>Test Email Successful!</h2>
                    </div>
                    <div style="padding: 20px;">
                        <p>This is a test email from <b>DR. NILESH SHAH'S MARKET ANALYSIS</b>.</p>
                        <p>If you received this, your email is configured correctly!</p>
                        <br>
                        <table style="border-collapse: collapse; width: 100%;">
                            <tr><td style="padding: 8px; border: 1px solid #ddd;"><b>From:</b></td><td style="padding: 8px; border: 1px solid #ddd;">{email_config.sender_email}</td></tr>
                            <tr><td style="padding: 8px; border: 1px solid #ddd;"><b>To:</b></td><td style="padding: 8px; border: 1px solid #ddd;">{', '.join(email_config.receiver_emails)}</td></tr>
                            <tr><td style="padding: 8px; border: 1px solid #ddd;"><b>Server:</b></td><td style="padding: 8px; border: 1px solid #ddd;">{email_config.smtp_server}:{email_config.smtp_port}</td></tr>
                            <tr><td style="padding: 8px; border: 1px solid #ddd;"><b>Time:</b></td><td style="padding: 8px; border: 1px solid #ddd;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                        </table>
                    </div>
                    <div style="background: #1f2937; color: #9ca3af; padding: 15px; text-align: center; font-size: 11px;">
                        DR. NILESH SHAH'S MARKET ANALYSIS | For educational purposes only
                    </div>
                </body>
                </html>
                """
                
                msg.attach(MIMEText(body, 'html'))
                
                if email_config.smtp_port == 465:
                    server = smtplib.SMTP_SSL(email_config.smtp_server, email_config.smtp_port, timeout=30)
                else:
                    server = smtplib.SMTP(email_config.smtp_server, email_config.smtp_port, timeout=30)
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                
                server.login(email_config.sender_email, email_config.sender_password)
                server.send_message(msg)
                server.quit()
                
                self.status_lbl.configure(text="Ready")
                messagebox.showinfo("Success!", 
                    f"Test email sent successfully!\n\n"
                    f"From: {email_config.sender_email}\n"
                    f"To: {', '.join(email_config.receiver_emails)}\n\n"
                    f"Check your inbox (and spam/junk folder)!")
                self._update_email_status()
                
            except smtplib.SMTPAuthenticationError as e:
                self.status_lbl.configure(text="Ready")
                messagebox.showerror("Authentication Failed", 
                    "Email login failed!\n\n"
                    "For GMAIL users:\n"
                    "1. You need an App Password (not regular password)\n"
                    "2. Go to: https://myaccount.google.com/apppasswords\n"
                    "3. Or: Google Account > Security > App Passwords\n"
                    "4. Generate password for 'Mail'\n"
                    "5. Use that 16-character password in the app\n\n"
                    "Requirements:\n"
                    "- 2-Factor Authentication must be enabled\n"
                    "- Use the 16-char App Password, not your login password\n\n"
                    f"Error details: {e}")
                
            except smtplib.SMTPConnectError as e:
                self.status_lbl.configure(text="Ready")
                messagebox.showerror("Connection Failed",
                    f"Cannot connect to email server!\n\n"
                    f"Server: {email_config.smtp_server}:{email_config.smtp_port}\n\n"
                    "Common fixes:\n"
                    "1. Check internet connection\n"
                    "2. Check SMTP server address\n"
                    "3. Try different port (587 or 465)\n"
                    "4. Check firewall settings\n\n"
                    f"Error: {e}")
                
            except Exception as e:
                self.status_lbl.configure(text="Ready")
                messagebox.showerror("Error", f"Failed to send email:\n{type(e).__name__}: {e}")
                
        except ImportError:
            messagebox.showerror("Error", "Daily report module not found!")
        except Exception as e:
            self.status_lbl.configure(text="Ready")
            messagebox.showerror("Error", f"Email test failed: {e}")
            import traceback
            traceback.print_exc()
    
    def save_schedule(self):
        """Save auto-report schedule (and keep the Windows task, if installed, in sync)."""
        config = {
            'enabled': self.auto_report_var.get(),
            'hour': int(self.report_hour_var.get()),
            'minute': int(self.report_min_var.get()),
            'report_type': self.report_type_var.get(),
        }

        try:
            with open(SCHEDULE_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
            return

        task_msg = ""
        if SCHEDULER_OK and scheduled_report.task_status():
            if config['enabled']:
                ok, m = scheduled_report.install_task(config['hour'], config['minute'])
                task_msg = f"\n\nWindows task updated: {m}" if ok else f"\n\nWindows task update FAILED: {m}"
            else:
                ok, m = scheduled_report.remove_task()
                task_msg = "\n\nWindows task removed." if ok else f"\n\nCould not remove Windows task: {m}"

        if config['enabled']:
            msg = f"Schedule saved! Report will be emailed on trading days at {config['hour']:02d}:{config['minute']:02d}."
            if not task_msg:
                msg += ("\n\nNote: without the Windows task the app must be open at that time.\n"
                        "Click 'Install Windows Task' to send it even when the app is closed.")
        else:
            msg = "Schedule saved (auto-report is disabled)."
        messagebox.showinfo("Success", msg + task_msg)
        self._update_task_status()

    def install_windows_task(self):
        """Register a weekday Windows Task Scheduler job that emails the report without the app open."""
        if not SCHEDULER_OK:
            messagebox.showerror("Error", "scheduled_report.py is missing.")
            return
        if REPORT_OK and not EmailConfig().is_configured:
            messagebox.showwarning("Email Not Configured",
                "Set up and test your email first (Email Report Configuration above), then install the task.")
            return
        self.auto_report_var.set(True)
        hour, minute = int(self.report_hour_var.get()), int(self.report_min_var.get())
        try:
            with open(SCHEDULE_FILE, 'w') as f:
                json.dump({'enabled': True, 'hour': hour, 'minute': minute,
                           'report_type': self.report_type_var.get()}, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save schedule: {e}")
            return
        ok, msg = scheduled_report.install_task(hour, minute)
        if ok:
            messagebox.showinfo("Windows Task Installed",
                f"{msg}.\n\nThe report will be emailed on NSE trading days even when this app is closed "
                "(weekends and NSE holidays are skipped).\n\n"
                "Your PC must be switched on and you must be logged in at that time.")
        else:
            messagebox.showerror("Task Install Failed", msg)
        self._update_task_status()

    def remove_windows_task(self):
        if not SCHEDULER_OK:
            return
        ok, msg = scheduled_report.remove_task()
        if ok:
            messagebox.showinfo("Removed", "Windows task removed.\nThe report will only be sent while the app is open.")
        else:
            messagebox.showwarning("Not Removed", msg)
        self._update_task_status()

    def _update_task_status(self):
        if not hasattr(self, 'task_status_lbl'):
            return
        status = scheduled_report.task_status() if SCHEDULER_OK else None
        if status:
            self.task_status_lbl.configure(text=f"Windows task: INSTALLED  |  next run: {status}", fg=THEME['success'])
        else:
            self.task_status_lbl.configure(text="Windows task: not installed (report is only sent while the app is open)",
                                           fg=THEME['fg3'])

    @staticmethod
    def _load_schedule_config():
        config = {'enabled': False, 'hour': 18, 'minute': 0, 'report_type': 'Indian + US'}
        try:
            if SCHEDULE_FILE.exists():
                with open(SCHEDULE_FILE, 'r') as f:
                    data = json.load(f)
                config['enabled'] = bool(data.get('enabled', False))
                config['hour'] = int(data.get('hour', 18))
                config['minute'] = int(data.get('minute', 0))
                config['report_type'] = data.get('report_type', 'Indian + US')
        except Exception as e:
            logger.error(f"Schedule config load error: {e}")
        return config

    def _check_auto_report(self):
        """Runs every 30s while the app is open: sends the scheduled report once per trading day.
        (Shares the sent-today marker and lock with the Windows task, so it's never sent twice.)"""
        try:
            sched = self._load_schedule_config()
            now = datetime.now()
            due = now.replace(hour=sched['hour'], minute=sched['minute'], second=0, microsecond=0)
            # 10-minute window so a report isn't fired hours late when the app is opened after the scheduled time
            if (sched['enabled'] and REPORT_OK and SCHEDULER_OK and not self._auto_report_running
                    and self._last_auto_report_date != now.date()
                    and due <= now < due + timedelta(minutes=10)):
                self._last_auto_report_date = now.date()
                self._run_auto_report(sched['report_type'])
        except Exception as e:
            logger.error(f"Auto-report check error: {e}")
        self.root.after(30000, self._check_auto_report)

    def _run_auto_report(self, report_type):
        watchlist = list(self.watchlist)
        self._auto_report_running = True
        self.status_lbl.configure(text="Auto-report: generating...")
        logger.info(f"Auto-report started ({report_type})")

        def work():
            try:
                sent, msg = scheduled_report.run_scheduled_report(watchlist=watchlist, report_type=report_type)
            except Exception as e:
                msg = f"Auto-report failed: {e}"
            logger.info(f"Auto-report: {msg}")

            def done():
                self._auto_report_running = False
                self.status_lbl.configure(text=f"Auto-report: {msg}"[:90])
            self.gui.schedule(done)

        threading.Thread(target=work, daemon=True).start()

    def apply_weights(self):
        try:
            weights = {k: v.get() for k, v in self.weight_vars.items()}
        except tk.TclError:
            messagebox.showwarning("Warning", "Weights must be whole numbers!")
            return
        total = sum(weights.values())
        if total != 100:
            messagebox.showwarning("Warning", f"Weights must total 100%! Current: {total}")
            return
        self._set_weights(weights, {'source': 'manual', 'applied': datetime.now().strftime('%Y-%m-%d')})
        messagebox.showinfo("Success", "Weights applied and saved!\n\nRe-scan (F5) to see updated scores.")

    def reset_weights(self):
        self._set_weights(dict(Scorer.DEFAULT_WEIGHTS), {'source': 'default', 'applied': datetime.now().strftime('%Y-%m-%d')})
        messagebox.showinfo("Reset", "Default weights restored.\n\nRe-scan (F5) to see updated scores.")

    def _set_weights(self, weights, meta=None):
        """Use these weights for scoring from now on, and remember them (and where they came from)."""
        try:
            save_weights(weights, meta)
        except Exception as e:
            Scorer.WEIGHTS.update(weights)
            logger.error(f"Could not save weights: {e}")
        if hasattr(self, 'weight_vars'):
            for k, v in weights.items():
                if k in self.weight_vars:
                    self.weight_vars[k].set(v)
        self._update_weights_status()

    @staticmethod
    def _load_app_settings():
        return load_app_settings()

    def _save_app_setting(self, **values):
        settings = self._load_app_settings()
        settings.update(values)
        try:
            with open(APP_SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save settings: {e}")

    # ---------- appearance: light / dark, animations ----------

    def toggle_animations(self):
        on = bool(self.animations_var.get())
        self._save_app_setting(animations=on)
        ui.Motion.enabled = on and ui.windows_allows_animation()
        if on:
            self._update_market_light()

    def apply_appearance(self, mode):
        """Switch between the light (Daylight) and dark looks. The window fades out, is rebuilt
        in the new colours with everything still in it, and fades back in."""
        if mode == THEME['mode']:
            return
        if self.scanning or self.bt_run_btn.cget('text') == "RUNNING...":
            self.toast("Change the look after the scan", "A scan or backtest is running - switch when it's done.", kind='warn')
            return
        self._save_app_setting(appearance=mode)

        def swap():
            state = self._capture_ui_state()
            THEME.clear()
            THEME.update(ui.palette(mode))
            ui.style_ttk(self.root, THEME)
            self.markers = ui.marker_images(THEME)
            ui.Toast._open.clear()
            for w in self.root.winfo_children():
                if not isinstance(w, tk.Toplevel):      # open pop-up windows stay open
                    w.destroy()
            self._scroll_canvases = []
            self._pulsing = None
            self.build_ui()
            self._restore_ui_state(state)
            ui.fade_window(self.root, 0.4, 1.0, 260)
            self.toast("Dark mode on" if mode == 'dark' else "Light mode on", "Change it any time in Settings > Appearance.", ms=3500)

        if ui.Motion.enabled:
            ui.fade_window(self.root, 1.0, 0.4, 160, done=swap)
        else:
            swap()

    def _capture_ui_state(self):
        """What the window shows, so a rebuild (light/dark switch) can put it all back."""
        old = dict(THEME)
        def label(w):
            return (w.cget('text'), w.cget('fg')) if w is not None and w.winfo_exists() else None
        def rows(tree):
            return [(tree.item(i, 'values'), tree.item(i, 'tags')) for i in tree.get_children()]
        return {
            'theme': old, 'tab': self.nb.index('current'),
            'sector': self.sector_var.get(), 'group': self.group_var.get(),
            'search': self.search_var.get(), 'filter': self.result_filter_var.get(),
            'hide_illiquid': self.hide_illiquid_var.get(),
            'bt': (self.bt_liquid_var.get(), self.bt_history_var.get(), self.bt_horizon_var.get(),
                   self._bt_result, self._bt_cache, self.bt_apply_btn.cget('state')),
            'chart_period': self.chart_period_var.get(), 'chart': self._chart_state,
            'labels': {name: label(getattr(self, name, None)) for name in
                       ('status_lbl', 'last_scan_lbl', 'cache_lbl', 'corp_status', 'corp_source_lbl', 'bt_status', 'bt_summary')},
            'corp_stats': {k: label(v) for k, v in self.corp_stats_labels.items()},
            'corp_rows': rows(self.corp_tree), 'corp_list': list(self.corp_listbox.get(0, tk.END)),
            'corp_filter': self.corp_filter_var.get(), 'progress': self.progress['value'],
            'sector_last': self._sector_last,
        }

    def _restore_ui_state(self, st):
        old = {v.lower(): k for k, v in st['theme'].items() if isinstance(v, str) and v.startswith('#')}
        def recolour(c):     # a colour from the old theme -> the same role in the new one
            key = old.get(str(c).lower())
            return THEME.get(key, c) if key else c
        for name, val in st['labels'].items():
            w = getattr(self, name, None)
            if val and w is not None:
                w.configure(text=val[0], fg=recolour(val[1]))
        for k, val in st['corp_stats'].items():
            if val and k in self.corp_stats_labels:
                self.corp_stats_labels[k].configure(text=val[0], fg=recolour(val[1]))
        for values, tags in st['corp_rows']:
            self.corp_tree.insert('', tk.END, values=values, tags=tags)
        for item in st['corp_list']:
            self.corp_listbox.insert(tk.END, item)
        self.corp_filter_var.set(st['corp_filter'])
        self.progress['value'] = st['progress']

        self.sector_var.set(st['sector'])
        self.group_var.set(st['group'])
        self.refresh_watchlist()
        self.hide_illiquid_var.set(st['hide_illiquid'])
        self.result_filter_var.set(st['filter'])
        self.search_var.set(st['search'])         # its trace refills the results table
        self.filter_results()
        if self.results:
            self.update_dash(animate=False)

        liquid, history, horizon, result, cache, apply_state = st['bt']
        self.bt_liquid_var.set(liquid)
        self.bt_history_var.set(history)
        self.bt_horizon_var.set(horizon)
        self._bt_cache = cache
        if result:
            self._show_backtest(result)
            self.bt_apply_btn.configure(state=apply_state)
        if st['sector_last']:
            self._show_sectors(*st['sector_last'])

        sym = getattr(self, '_detail_symbol', None)
        r = next((x for x in self.results if x['symbol'] == sym), None) if sym else None
        if r:
            self.update_breakdown(r)
            self.update_targets(r)
            self.update_patterns(r)
        self.chart_period_var.set(st['chart_period'])
        chart = st['chart']
        if chart and chart[0] == 'stock':
            self._render_stock_chart(*chart[1:], animate=False)
        elif chart and chart[0] == 'map':
            self.show_market_map()
        self._update_market_light()
        self.nb.select(st['tab'])

    # ---------- weights from the backtest: status + monthly re-check ----------

    WEIGHTS_RECHECK_DAYS = 30

    @staticmethod
    def _weights_meta():
        meta = load_app_settings().get('weights_meta') or {}
        if not meta:   # no record yet: describe what's in use
            meta = {'source': 'default' if Scorer.WEIGHTS == Scorer.DEFAULT_WEIGHTS else 'manual'}
        return meta

    def _update_weights_status(self):
        if not hasattr(self, 'bt_weights_lbl'):
            return
        meta, T = self._weights_meta(), THEME
        source = meta.get('source')
        color = T['fg']
        if source == 'backtest':
            text = (f"Scoring weights: SUGGESTED by the backtest (applied {meta.get('applied', '?')}, "
                    f"{meta.get('horizon', 10)}-day holding).")
            last = meta.get('last_result') or {}
            if last.get('verdict') == 'worse':
                text += (f"  Re-check {meta.get('last_check')}: the DEFAULT weights did better over {last.get('since')} to "
                         f"{last.get('until')} (power {last.get('default_ic', 0):+.3f} vs yours {last.get('current_ic', 0):+.3f}). "
                         "Consider Settings > Reset Defaults, or re-run the backtest and apply fresh suggestions.")
                color = T['warning']
            elif last.get('verdict') == 'ok':
                text += (f"  Re-check {meta.get('last_check')}: still at least as good as the defaults "
                         f"(power {last.get('current_ic', 0):+.3f} vs {last.get('default_ic', 0):+.3f}).")
                color = T['success']
            try:
                due = datetime.strptime(meta.get('last_check') or meta.get('applied'), '%Y-%m-%d') + timedelta(days=self.WEIGHTS_RECHECK_DAYS)
                text += f"  Next automatic re-check: {due:%Y-%m-%d}."
            except (TypeError, ValueError):
                pass
        elif source == 'manual':
            when = f" on {meta['applied']}" if meta.get('applied') else ""
            text = f"Scoring weights: set manually{when}. 'Re-check Weights' compares them with the defaults on recent history."
        else:
            text = "Scoring weights: DEFAULT. Run a backtest, then 'Apply Suggested Weights' to tune them to your stocks."
        self.bt_weights_lbl.configure(text=text, fg=color)

    def recheck_weights(self, auto=False):
        """Compare the weights in use with the defaults on the most recent ~6 months of history."""
        if not BACKTEST_OK or not MARKET_DATA_OK or not self.watchlist:
            return
        if Scorer.WEIGHTS == Scorer.DEFAULT_WEIGHTS:
            if not auto:
                messagebox.showinfo("Re-check Weights", "You're using the default weights - nothing to compare.\n\n"
                                    "Run a backtest and click 'Apply Suggested Weights' to tune them to your stocks.")
            return
        if getattr(self, '_recheck_running', False):
            return
        self._recheck_running = True
        meta = self._weights_meta()
        horizon, years = int(meta.get('horizon', 10)), int(meta.get('years', 5))
        min_liq = self.min_liquidity_cr if meta.get('liquid_only') else 0
        watchlist, current = list(self.watchlist), dict(Scorer.WEIGHTS)
        self.bt_weights_lbl.configure(text="Re-checking the scoring weights on recent history...", fg=THEME['fg3'])

        def work():
            try:
                data = market_data.load_history(watchlist, years=HISTORY_YEARS)
                data = {s: market_data.slice_period(df, f"{years}y") for s, df in data.items()}
                samples, _ = backtest.build_samples(data, Scorer)
                result = backtest.compare_weights(samples, current, dict(Scorer.DEFAULT_WEIGHTS), horizon,
                                                  min_liquidity_cr=min_liq)
            except Exception as e:
                result = {'error': str(e)}
            self.gui.schedule(self._recheck_done, result, auto)
        threading.Thread(target=work, daemon=True).start()

    def _recheck_done(self, result, auto):
        self._recheck_running = False
        if 'error' in result:
            logger.error(f"Weights re-check failed: {result['error']}")
            self._update_weights_status()
            if not auto:
                messagebox.showerror("Re-check Weights", f"Re-check failed: {result['error']}")
            return
        cur, dflt = result['a'], result['b']
        verdict = 'worse' if cur['ic'] < dflt['ic'] - 0.01 else 'ok'
        settings = load_app_settings()
        meta = settings.get('weights_meta') or self._weights_meta()
        meta['last_check'] = datetime.now().strftime('%Y-%m-%d')
        meta['last_result'] = {'verdict': verdict, 'since': result['since'], 'until': result['until'],
                               'current_ic': round(cur['ic'], 4), 'default_ic': round(dflt['ic'], 4),
                               'current_spread': round(cur['spread'], 3), 'default_spread': round(dflt['spread'], 3),
                               'samples': result['n_samples']}
        settings['weights_meta'] = meta
        try:
            save_app_settings(settings)
        except Exception as e:
            logger.error(f"Could not save re-check result: {e}")
        logger.info(f"Weights re-check: {verdict} (yours {cur['ic']:+.3f} vs default {dflt['ic']:+.3f})")
        self._update_weights_status()
        summary = (f"Recent history {result['since']} to {result['until']} ({result['n_samples']:,} stock-days, "
                   f"{result['horizon']}-day holding):\n\n"
                   f"Your weights:      power {cur['ic']:+.3f}, best-vs-worst {cur['spread']:+.2f}%\n"
                   f"Default weights:  power {dflt['ic']:+.3f}, best-vs-worst {dflt['spread']:+.2f}%\n\n")
        if verdict == 'worse':
            messagebox.showwarning("Scoring Weights Re-check", summary +
                                   "The DEFAULT weights predicted better recently. Consider Settings > Reset Defaults, "
                                   "or re-run the backtest and apply fresh suggestions.")
        elif not auto:
            messagebox.showinfo("Scoring Weights Re-check", summary + "Your weights are still at least as good as the defaults.")

    def _auto_recheck_weights(self):
        """Runs after start-up: re-checks weights applied from the backtest every 30 days."""
        meta = self._weights_meta()
        if meta.get('source') != 'backtest':
            return
        try:
            last = datetime.strptime(meta.get('last_check') or meta.get('applied'), '%Y-%m-%d')
        except (TypeError, ValueError):
            last = datetime.min
        if (datetime.now() - last).days >= self.WEIGHTS_RECHECK_DAYS:
            if self.scanning:
                self.root.after(60000, self._auto_recheck_weights)   # don't compete with a scan
            else:
                self.recheck_weights(auto=True)

    def save_liquidity_setting(self):
        try:
            value = float(self.min_liquidity_var.get())
            if value < 0:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showwarning("Warning", "Enter a number of Rs crore, e.g. 1 or 0.5")
            return
        self.min_liquidity_cr = value
        settings = self._load_app_settings()
        settings['min_liquidity_cr'] = value
        try:
            with open(APP_SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
            return
        if REPORT_OK:
            import daily_report
            daily_report.MIN_LIQUIDITY_CR = value   # module read the old value when it was imported
        self.hide_illiquid_cb.configure(text=f"Hide illiquid (< Rs {value:g} Cr/day)")
        if hasattr(self, 'bt_liquid_cb'):
            self.bt_liquid_cb.configure(text=f"Liquid stocks only (>= Rs {value:g} Cr/day)")
        self.filter_results()
        n = sum(1 for r in getattr(self, '_all_results', []) if self._is_illiquid(r))
        messagebox.showinfo("Saved", f"Stocks trading less than Rs {value:g} crore/day are now flagged as illiquid."
                            + (f"\n\n{n} stock(s) in the last scan are below this." if getattr(self, '_all_results', None) else ""))

    @staticmethod
    def _load_weights():
        """Load saved scoring weights (ignored unless they're complete and total 100)."""
        scoring.load_weights()

    def toggle_password_visibility(self):
        """Toggle password field visibility."""
        if hasattr(self, 'pw_entry') and hasattr(self, 'pw_visible'):
            self.pw_visible = not self.pw_visible
            if self.pw_visible:
                self.pw_entry.configure(show='')
            else:
                self.pw_entry.configure(show='*')
    
    def _load_email_config_to_fields(self):
        """Load existing email config into the settings fields."""
        try:
            if not REPORT_OK:
                return
            from daily_report import EmailConfig
            config = EmailConfig()
            
            if config.sender_email:
                self.email_vars['smtp_server'].set(config.smtp_server)
                self.email_vars['smtp_port'].set(str(config.smtp_port))
                self.email_vars['sender_email'].set(config.sender_email)
                self.email_vars['sender_password'].set(config.sender_password)
                self.email_vars['receiver_emails'].set(', '.join(config.receiver_emails) if config.receiver_emails else '')
        except Exception as e:
            print(f"Error loading email config to fields: {e}")
    
    def _update_email_status(self):
        """Update email status indicator."""
        try:
            if not REPORT_OK:
                if hasattr(self, 'email_status_lbl'):
                    self.email_status_lbl.configure(text="⚠ Daily report module not found", fg=THEME['danger'])
                return
            
            from daily_report import EmailConfig
            config = EmailConfig()
            
            if config.is_configured and config.sender_password:
                import daily_report
                where = "Windows Credential Manager" if daily_report.KEYRING_OK else "email_config.json (install 'keyring' for safer storage)"
                status = (f"✅ Email configured: {config.sender_email} → {', '.join(config.receiver_emails)}"
                          f"   |   password stored in {where}")
                color = THEME['success']
            elif config.is_configured:
                status = "⚠ Email configured but password is empty - please re-save"
                color = THEME['warning']
            else:
                status = "❌ Email not configured - fill in settings and click 'Save Email Config'"
                color = THEME['danger']
            
            if hasattr(self, 'email_status_lbl'):
                self.email_status_lbl.configure(text=status, fg=color)
        except Exception as e:
            if hasattr(self, 'email_status_lbl'):
                self.email_status_lbl.configure(text=f"⚠ Error: {e}", fg=THEME['danger'])
    
    def clear_email_config(self):
        """Clear email configuration."""
        if not messagebox.askyesno("Clear Email Config", 
            "Are you sure you want to clear email configuration?\n\n"
            "This will remove all saved email settings."):
            return
        
        try:
            if REPORT_OK:
                EmailConfig().delete_stored_password()   # also remove it from Windows Credential Manager
            config_file = str(DATA_DIR / "email_config.json")
            if os.path.exists(config_file):
                os.remove(config_file)
            
            # Clear fields
            self.email_vars['smtp_server'].set("smtp.gmail.com")
            self.email_vars['smtp_port'].set("587")
            self.email_vars['sender_email'].set("")
            self.email_vars['sender_password'].set("")
            self.email_vars['receiver_emails'].set("")
            
            self._update_email_status()
            messagebox.showinfo("Cleared", "Email configuration cleared.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear: {e}")
    
    def build_help_tab(self):
        """Build Help tab."""
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Help  ")
        self.help_tab = tab
        
        header = tk.Frame(tab, bg=T['bg2'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Help", bg=T['bg2'], fg=T['fg'],
                 font=(ui.DISPLAY, 14, 'bold')).pack(side=tk.LEFT, padx=16)
        
        canvas = tk.Canvas(tab, bg=T['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=T['bg'])
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._scroll_canvases.append(canvas)

        sections = [
            ("KEYBOARD SHORTCUTS", [
                ("F5", "Scan all stocks"), ("Ctrl+I", "Import"), ("Ctrl+S", "Save"),
                ("Ctrl+E", "Export Excel"), ("Ctrl+P", "Export PDF"),
                ("Ctrl+D", "Daily Report"), ("Ctrl+G", "New Group"),
                ("Ctrl+F", "Focus Search"), ("Ctrl+L", "View Log"),
                ("F1", "Help Tab"), ("Delete", "Delete stock"),
                ("Escape", "Close/Cancel"), ("Double-click", "View details"),
            ]),
            ("INDICATORS", [
                ("RSI", "Overbought >70, Oversold <30"), ("MACD", "Trend momentum"),
                ("SuperTrend", "Trend following"), ("VWAP", "Volume weighted price"),
                ("Bollinger", "Volatility bands"), ("ADX", "Trend strength")
            ]),
            ("SCORING", [
                ("75-100", "STRONG BUY"), ("60-74", "BUY"), ("45-59", "HOLD"),
                ("30-44", "SELL"), ("0-29", "STRONG SELL")
            ]),
            ("STOP-LOSS & TARGETS", [
                ("Stop-loss", "Just beyond the nearest support (the nearest resistance, for a SELL)"),
                ("Targets 1-3", "The next resistance levels above the price (supports below, for a SELL)"),
                ("Levels", "Swing highs and lows of the last year; turns close together count as one level"),
                ("No level", "Where a stock has no level within reach, a multiple of its ATR is used instead"),
                ("Risk : Reward", "Distance to Target 2 (Target 1 for a HOLD), divided by distance to the stop-loss"),
            ]),
            ("HOW TO USE", [
                ("1.", "Add stocks: type the first letters of the company's name and pick it from the list"),
                ("", "(the list shows its NSE and BSE symbols; typing a symbol or BSE code works too)"),
                ("2.", "Organize with Groups (Ctrl+G)"),
                ("3.", "Click Scan (F5)"), ("4.", "View results & details"),
                ("5.", "Check Sector Rotation for trends"), ("6.", "Export reports (Ctrl+P)")
            ]),
            ("WATCHLIST GROUPS", [
                ("Favorites", "Your top picks"),
                ("Swing Trades", "Short-term trades"),
                ("Long Term", "Investment picks"),
                ("Dividend Picks", "Income stocks"),
                ("Custom", "Create your own groups (Ctrl+G)"),
            ]),
            ("MARKET COMPARISON & HISTORY", [
                ("vs Nifty 3M", "Stock's 3-month return minus the Nifty 50's (+5% = beat the market by 5 points)"),
                ("Score Chg", "Change in score since the previous scan day ('new' = first scan)"),
                ("Signal changes", "Listed after each scan and in the watchlist email"),
                ("Score history", "Chart under Score Breakdown; all scans are in score_history.csv"),
                ("Re-check Weights", "Backtest tab: compares your weights with the defaults (automatic monthly)"),
            ]),
            ("NEW LISTINGS", [
                ("Candle: 1 Hour", "Stock listed less than a month ago - every indicator uses 1-hour candles"),
                ("Candle: Daily", "All other stocks - indicators use daily candles"),
                ("From day 3", "A new listing gets a score once it has 20 hourly candles (3 trading days)"),
                ("Targets", "From hourly price swings, so stop-loss and targets sit closer to the price"),
                ("vs Nifty", "N/A until the stock has traded for the full period"),
            ]),
            ("LIQUIDITY", [
                ("Traded/day (Cr)", "Average daily traded value over the last 20 sessions, in Rs crore"),
                ("LOW", "Below the Settings threshold - stop-loss/targets less reliable"),
                ("Hide illiquid", "Scan Results checkbox to hide LOW stocks"),
            ]),
            ("APPEARANCE & 3D", [
                ("Light / Dark", "Settings > Appearance switches between the light Daylight look and dark mode"),
                ("Animations", "Settings > Appearance turns the motion on or off (Windows' own setting is respected too)"),
                ("3D market map", "Charts tab: every scanned stock by score, RSI and strength vs the Nifty - drag to turn it"),
                ("3D sectors", "Sector tab: buy, hold and sell stocks in each sector, after Analyze"),
                ("Signal markers", "Scan Results: double up = strong buy, up = buy, bar = hold, down = sell, double down = strong sell"),
            ]),
            ("SECTOR ROTATION", [
                ("LEADING", "Scores above your watchlist's average and not falling - the strongest sectors"),
                ("WEAKENING", "Above average, but the score has fallen since last week - losing strength"),
                ("IMPROVING", "Below average, but the score has risen since last week - gaining strength"),
                ("LAGGING", "Below average and not rising - the weakest sectors"),
                ("Chg", "Change in the sector's average score against the scan of about a week earlier"),
            ]),
        ]
        
        for title, items in sections:
            sf = tk.LabelFrame(content, text=f" {title} ", bg=T['bg'], fg=T['gold'],
                              font=(ui.FONT, 12, 'bold'))
            sf.pack(fill=tk.X, padx=20, pady=10)
            for key, val in items:
                row = tk.Frame(sf, bg=T['card'], padx=10, pady=4)
                row.pack(fill=tk.X, padx=10, pady=2)
                tk.Label(row, text=key, bg=T['card'], fg=T['accent'],
                        font=(ui.FONT, 10, 'bold'), width=16, anchor=tk.W).pack(side=tk.LEFT)
                tk.Label(row, text=val, bg=T['card'], fg=T['fg'],
                        font=(ui.FONT, 10)).pack(side=tk.LEFT, padx=10)
    

    def _setup_market_status(self):
        """Keep the market status indicator up to date (every minute)."""
        self._update_market_light()
        self.root.after(60000, self._setup_market_status)

    def _update_market_light(self):
        try:
            now = datetime.now()
            # the saved holiday list only - _refresh_holidays downloads it, off the window's thread
            holidays = scheduled_report.cached_holidays(now.year) if SCHEDULER_OK else None
            is_open, text = market_status(now, holidays)
            color = THEME['buy'] if is_open else THEME['sell']
            self.market_dot.delete('all')
            self.market_dot.create_oval(5, 5, 13, 13, fill=color, outline='', tags='dot')
            self.market_status_lbl.configure(text=text, fg=THEME['fg2'])
            self._market_open = is_open
            if is_open:
                self._pulse_market_dot()
        except Exception as e:
            logger.warning(f"Market status error: {e}")

    def _pulse_market_dot(self):
        """While the market is open, a ring keeps rippling out of the green dot."""
        dot = self.market_dot
        if getattr(self, '_pulsing', None) is dot or not ui.Motion.enabled:
            return
        self._pulsing = dot
        T = THEME

        def ring(v):
            dot.delete('ring')
            r = 4 + 5 * v
            dot.create_oval(9 - r, 9 - r, 9 + r, 9 + r, outline=ui.blend(T['buy'], T['bg2'], v), width=2, tags='ring')
            dot.tag_raise('dot')

        def again():
            if dot.winfo_exists() and getattr(self, '_market_open', False) and ui.Motion.enabled:
                ui.tween(dot, 1500, ring, done=lambda: dot.after(700, again))
            else:
                if dot.winfo_exists():
                    dot.delete('ring')
                self._pulsing = None
        again()

    def _refresh_companies(self):
        try:
            if symbols.refresh_if_stale():
                self.gui.schedule(self.refresh_watchlist)      # names of newly listed companies
        except Exception as e:
            logger.warning(f"Company list refresh failed: {e}")

    def _refresh_holidays(self):
        """Download NSE's holiday list in the background if the saved one is over a week old, so
        the market light (and the scheduled report) know about holidays declared during the year."""
        if not SCHEDULER_OK:
            return
        def work():
            try:
                scheduled_report._nse_holidays(datetime.now().year)
                self.gui.schedule(self._update_market_light)
            except Exception as e:
                logger.warning(f"Holiday list refresh failed: {e}")
        threading.Thread(target=work, daemon=True).start()

    def _create_group(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("New Group", "Enter group name:", parent=self.root)
        if name and name.strip():
            name = name.strip()
            if name not in self.watchlist_groups:
                self.watchlist_groups[name] = []
                self.group_cb.configure(values=list(self.watchlist_groups.keys()))
                self.save_watchlist_groups()
                # Stay on the current list (a new group is empty, so switching to it shows nothing)
                messagebox.showinfo("Group Created", f"Group '{name}' created.\n\n"
                                    f"To fill it: show 'All Stocks', select a stock and click 'Add to Group'.")

    def _add_to_group(self):
        sel = self.wl_list.curselection()
        if not sel:
            messagebox.showinfo("Info", "Select a stock first!")
            return
        stock = self._wl_symbol(self.wl_list.get(sel[0]))
        group = self.group_var.get()
        if group == 'All Stocks':
            # The list shows every stock here - ask which group to add to. (Picking a group in
            # the dropdown filters the list to that group's members, so it can't be used for this.)
            group = self._ask_group(stock)
            if not group:
                return
        members = self.watchlist_groups.setdefault(group, [])
        if stock in members:
            messagebox.showinfo("Info", f"{stock} is already in '{group}'")
            return
        members.append(stock)
        self.save_watchlist_groups()
        self.refresh_watchlist()
        messagebox.showinfo("Added", f"{stock} added to '{group}'")
    
    def _ask_group(self, stock):
        """Small dialog: which group should this stock go into? Returns the name or None."""
        groups = [g for g in self.watchlist_groups if g != 'All Stocks']
        if not groups:
            messagebox.showinfo("Info", "Create a group first (New Group).")
            return None
        T = THEME
        dlg = tk.Toplevel(self.root)
        dlg.title("Add to Group")
        dlg.configure(bg=T['bg'])
        ui.set_titlebar(dlg, T['mode'] == 'dark')
        dlg.transient(self.root)
        dlg.resizable(False, False)
        tk.Label(dlg, text=f"Add {stock} to which group?", bg=T['bg'], fg=T['fg'],
                 font=(ui.FONT, 11)).pack(padx=25, pady=(18, 6))
        var = tk.StringVar(value=groups[0])
        ttk.Combobox(dlg, textvariable=var, values=groups, state='readonly', width=24).pack(padx=25, pady=4)
        result = {}
        def ok():
            result['group'] = var.get()
            dlg.destroy()
        row = tk.Frame(dlg, bg=T['bg'])
        row.pack(pady=15)
        self.btn(row, "Add", T['success'], ok).pack(side=tk.LEFT, padx=5)
        self.btn(row, "Cancel", T['bg3'], dlg.destroy).pack(side=tk.LEFT, padx=5)
        dlg.bind('<Return>', lambda e: ok())
        dlg.bind('<Escape>', lambda e: dlg.destroy())
        dlg.grab_set()
        self.root.wait_window(dlg)
        return result.get('group')

    def _remove_from_group(self):
        sel = self.wl_list.curselection()
        if not sel:
            return
        stock = self._wl_symbol(self.wl_list.get(sel[0]))
        group = self.group_var.get()
        if group == 'All Stocks':
            messagebox.showinfo("Info", "Can't remove from 'All Stocks'")
            return
        if stock in self.watchlist_groups.get(group, []):
            self.watchlist_groups[group].remove(stock)
            self.save_watchlist_groups()
            self._switch_group()

    def _switch_group(self):
        self.current_group = self.group_var.get()
        self.refresh_watchlist()

    def save_watchlist_groups(self):
        try:
            write_json(BASE_DIR / "watchlist_groups.json", self.watchlist_groups, indent=2)
        except Exception as e:
            logger.error(f"Could not save watchlist groups: {e}")

    def load_watchlist_groups(self):
        try:
            fp = BASE_DIR / "watchlist_groups.json"
            if fp.exists():
                with open(fp, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.watchlist_groups.update(data)
        except: pass

    def _on_escape(self):
        for w in self.root.winfo_children():
            if isinstance(w, tk.Toplevel) and w.state() == 'normal':     # not the hidden suggestion list
                w.destroy()
                return
        if hasattr(self, 'search_var'):
            self.search_var.set("")

    def _select_all_results(self):
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children)

    def _company_rows(self, text):
        """Rows for the list under the "Add a stock" box: company, NSE symbol, BSE symbol (code)."""
        rows = []
        for e in symbols.search(text, 8):
            have = e[symbols.ADD] in self.watchlist
            nse = (e[symbols.NSE] + ('  (SME)' if e[symbols.ADD].endswith('-SM') else '')) if e[symbols.NSE] else 'not listed'
            bse = f"{e[symbols.BSE]}  ({e[symbols.CODE]})" if e[symbols.BSE] else 'not listed'
            rows.append(((e[symbols.NAME] + ('   (in your watchlist)' if have else ''), nse, bse), e, 'dim' if have else ''))
        return rows

    def _add_company(self, e):
        self._add_symbol(e[symbols.ADD], e[symbols.NAME])

    def add_stock(self):
        """Add what is in the typing box. A company highlighted in the list under it is added;
        so is a symbol or BSE code typed in full. Anything else opens the list to choose from;
        a symbol the list doesn't know (a stock listed in the last few days) is added as typed."""
        text = self.entry.get().strip()
        if not text:
            return
        if self.suggest is not None:
            picked = self.suggest.selected()
            if picked is None:
                matches = symbols.search(text, 8)
                typed = text.upper().replace(' ', '')
                exact = [e for e in matches if typed in (e[symbols.NSE], e[symbols.BSE], e[symbols.CODE], e[symbols.ADD])]
                if exact:
                    picked = exact[0]
                elif matches:
                    self.suggest.update()        # show them: Enter again (or a click) adds the highlighted one
                    return
            if picked is not None:
                self.suggest.hide()
                self._add_company(picked)
                return
            if ' ' in text:
                self.toast("No company found", "Check the spelling, or type the stock's exchange symbol.", kind='warn', ms=4000)
                return
        s = re.sub(r'[^A-Z0-9&-]', '', text.upper())
        if not s or len(s) < 2: return
        self._add_symbol(s)

    def _add_symbol(self, s, name=''):
        if s in self.watchlist:
            messagebox.showinfo("Info", f"{s} already in list!")
            return
        self.watchlist.append(s)
        self.entry.delete(0, tk.END)
        if self.suggest is not None:
            self.suggest.hide()
        self.refresh_watchlist()
        self.save_watchlist()
        if name:
            self.toast(f"Added {s}", name, kind='good', ms=3000)
    
    def del_stock(self):
        sel = self.wl_list.curselection()
        if not sel: return
        s = self._wl_symbol(self.wl_list.get(sel[0]))
        if s in self.watchlist:
            self.watchlist.remove(s)
        for members in self.watchlist_groups.values():
            if s in members:
                members.remove(s)
        self.save_watchlist_groups()
        self.refresh_watchlist()
        self.save_watchlist()
    
    def clear_list(self):
        if messagebox.askyesno("Confirm", "Clear all?"):
            self.watchlist.clear()
            for members in self.watchlist_groups.values():   # as Delete does: or a stock added again
                members.clear()                              # later would reappear in its old groups
            self.save_watchlist_groups()
            self.refresh_watchlist()
            self.save_watchlist()
    
    def refresh_watchlist(self):
        group = getattr(self, 'current_group', 'All Stocks')
        if group == 'All Stocks':
            base_stocks = list(self.watchlist)
        else:
            base_stocks = [s for s in self.watchlist if s in self.watchlist_groups.get(group, [])]
        
        sector = self.sector_var.get()
        if sector == "All":
            stocks = sorted(base_stocks)
        elif sector in SECTOR_MAP:
            stocks = sorted([s for s in base_stocks if s in SECTOR_MAP[sector]])
        else:
            stocks = sorted(base_stocks)
        
        self.wl_list.delete(0, tk.END)
        for s in stocks:
            grps = [g for g, m in self.watchlist_groups.items() if s in m and g != 'All Stocks']
            tag = f"  [{', '.join(grps)}]" if grps else ""
            name = symbols.name_of(s) if SYMBOLS_OK else ''
            self.wl_list.insert(tk.END, f"{s}{'  ' + name if name else ''}{tag}")   # _wl_symbol() reads up to the first gap
        self.wl_count.configure(text=f"Stocks: {len(stocks)}")
        if hasattr(self, 'group_count_lbl'):
            self.group_count_lbl.configure(text=f"Group: {group} | {len(stocks)} stocks")
    
    def save_watchlist(self):
        try:
            write_json(WATCHLIST_FILE, self.watchlist)
        except Exception as e:
            logger.error(f"Could not save the watchlist: {e}")

    def load_watchlist(self):
        try:
            if WATCHLIST_FILE.exists():
                with open(WATCHLIST_FILE, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.watchlist = data
        except Exception as e:
            logger.error(f"Could not read the watchlist ({e}) - starting with an empty one")
            self.watchlist = []
    
    def save_list(self):
        if not self.watchlist:
            messagebox.showwarning("Warning", "List is empty!")
            return
        fp = filedialog.asksaveasfilename(defaultextension=".json", initialfile="my_watchlist.json",
                                         filetypes=[("JSON", "*.json"), ("CSV", "*.csv"), ("Text", "*.txt")])
        if not fp: return
        try:
            if fp.endswith('.json'):
                with open(fp, 'w') as f:
                    json.dump({'watchlist': self.watchlist, 'date': str(datetime.now()), 'app': "DR. NILESH SHAH'S Analysis"}, f, indent=2)
            elif fp.endswith('.csv'):
                with open(fp, 'w', newline='') as f:
                    csv.writer(f).writerows([[s] for s in self.watchlist])
            else:
                with open(fp, 'w') as f:
                    f.write('\n'.join(sorted(self.watchlist)))
            messagebox.showinfo("Saved", f"Saved {len(self.watchlist)} stocks!")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def import_list(self):
        fp = filedialog.askopenfilename(filetypes=[("All", "*.xlsx *.xls *.pdf *.json *.csv *.txt"),
                                                   ("Excel", "*.xlsx *.xls"), ("PDF", "*.pdf"),
                                                   ("JSON", "*.json"), ("CSV", "*.csv"), ("Text", "*.txt")])
        if not fp: return
        
        imported = []
        ext = os.path.splitext(fp)[1].lower()
        
        try:
            if ext in ('.xlsx', '.xls'):
                df = pd.read_excel(fp, header=None)
                for col in df.columns:
                    for v in df[col].dropna():
                        s = str(v).strip().upper()
                        if self._looks_like_symbol(s):
                            imported.append(s)
            elif ext == '.pdf':
                if not PDF_OK:
                    messagebox.showerror("Error", "Install pdfplumber: pip install pdfplumber")
                    return
                with pdfplumber.open(fp) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            for w in text.split():
                                s = re.sub(r'[^A-Za-z0-9&-]', '', w.strip()).upper()
                                if self._looks_like_symbol(s):
                                    imported.append(s)
            # utf-8-sig: files saved by Excel ("CSV UTF-8") or Notepad start with an invisible
            # marker that used to stick to the first symbol and get it silently dropped
            elif ext == '.json':
                with open(fp, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                    imported = data.get('watchlist', data) if isinstance(data, dict) else data
            elif ext == '.csv':
                with open(fp, 'r', encoding='utf-8-sig', errors='replace', newline='') as f:
                    imported = [row[0] for row in csv.reader(f) if row]
            else:
                with open(fp, 'r', encoding='utf-8-sig', errors='replace') as f:
                    imported = [l.strip() for l in f if l.strip()]

            candidates = sorted({str(x).strip().upper() for x in imported if str(x).strip()} - set(self.watchlist))
            # column headings ("Symbol", "Stock" ...) look like symbols but aren't stocks
            candidates = [s for s in candidates if self._looks_like_symbol(s) and s not in self.IMPORT_HEADINGS]

            rejected = []
            if ext in ('.xlsx', '.xls', '.pdf') and candidates and MARKET_DATA_OK:
                # Excel cells / PDF words are guesses (headings like "Symbol", ordinary words):
                # keep only the ones Yahoo Finance knows as NSE/BSE stocks
                self.status_lbl.configure(text=f"Checking {len(candidates)} possible symbols...")
                self.root.update()
                new_listings = {}   # stocks with under 20 days of history are real stocks too
                found = set(market_data.load_history(candidates, years=HISTORY_YEARS, short=new_listings)) | set(new_listings)
                self.status_lbl.configure(text="Ready")
                if not found:
                    messagebox.showerror("Import", "Couldn't verify any symbols from this file.\n\n"
                                         "Check your internet connection, or import a CSV/TXT list instead.")
                    return
                rejected = [s for s in candidates if s not in found]
                candidates = [s for s in candidates if s in found]

            self.watchlist.extend(candidates)
            self.refresh_watchlist()
            self.save_watchlist()
            msg = f"Added {len(candidates)} stocks from {os.path.basename(fp)}"
            if rejected:
                shown = ', '.join(rejected[:15]) + (' ...' if len(rejected) > 15 else '')
                msg += f"\n\nSkipped {len(rejected)} entries that aren't NSE/BSE stocks:\n{shown}"
            messagebox.showinfo("Imported", msg)
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    IMPORT_HEADINGS = {'SYMBOL', 'SYMBOLS', 'STOCK', 'STOCKS', 'SCRIP', 'SCRIPS', 'TICKER', 'TICKERS', 'NAME', 'WATCHLIST'}

    @staticmethod
    def _looks_like_symbol(s):
        """NSE/BSE-style symbol: 2-20 chars of A-Z, 0-9, & or -, with at least one letter
        (e.g. RELIANCE, M&M, BAJAJ-AUTO, 20MICRONS). Pure numbers are allowed as BSE codes."""
        return bool(re.fullmatch(r'[A-Z0-9&-]{2,20}', s)) and (any(ch.isalpha() for ch in s) or s.isdigit())
    
    def export_results(self):
        if not self.results:
            messagebox.showwarning("Warning", "No results! Run scan first.")
            return
        fp = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="DR_Nilesh_Shah_Results.xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")])
        if not fp: return
        try:
            if fp.endswith('.xlsx'):
                wb = Workbook()
                ws = wb.active
                ws.title = "DR. NILESH SHAH ANALYSIS"
                headers = ['Symbol', 'Price', 'Change%', 'RSI', 'Score', 'Recommendation', 'Stop Loss', 'Target 1', 'Target 2', 'Risk:Reward',
                           'Traded/day (Rs Cr)', 'Liquidity', 'vs Nifty 1M (%)', 'vs Nifty 3M (%)', 'vs Nifty 6M (%)',
                           'Score Chg', 'Previous Signal', 'Candle']
                for i, h in enumerate(headers, 1):
                    c = ws.cell(row=1, column=i, value=h)
                    c.font = Font(bold=True, color="FFFFFF")
                    c.fill = PatternFill(start_color="1f6feb", end_color="1f6feb", fill_type="solid")
                for row, r in enumerate(self.results, 2):
                    t = r.get('targets', {})
                    ws.cell(row=row, column=1, value=r['symbol'])
                    ws.cell(row=row, column=2, value=round(r['price'], 2))
                    ws.cell(row=row, column=3, value=round(r['change'], 2))
                    ws.cell(row=row, column=4, value=round(r['rsi'], 2))
                    ws.cell(row=row, column=5, value=r['score'])
                    ws.cell(row=row, column=6, value=r['rec'])
                    ws.cell(row=row, column=7, value=t.get('sl', ''))
                    ws.cell(row=row, column=8, value=t.get('t1', ''))
                    ws.cell(row=row, column=9, value=t.get('t2', ''))
                    ws.cell(row=row, column=10, value=f"1:{t.get('rr', 0)}")
                    ws.cell(row=row, column=11, value=round(r.get('data', {}).get('liquidity_cr', 0), 2))
                    ws.cell(row=row, column=12, value='LOW' if self._is_illiquid(r) else 'OK')
                    rs = r.get('rs') or {}
                    for col, period in ((13, '1M'), (14, '3M'), (15, '6M')):
                        ws.cell(row=row, column=col, value=rs.get(period))
                    if r.get('prev_score') is not None:
                        ws.cell(row=row, column=16, value=round(r['score'] - r['prev_score'], 1))
                        ws.cell(row=row, column=17, value=f"{r.get('prev_rec', '')} ({r.get('prev_date', '')})")
                    ws.cell(row=row, column=18, value='1 Hour' if r.get('hourly') else 'Daily')
                wb.save(fp)
            else:
                with open(fp, 'w', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(['Symbol', 'Price', 'Score', 'Recommendation'])
                    for r in self.results:
                        w.writerow([r['symbol'], round(r['price'], 2), r['score'], r['rec']])
            messagebox.showinfo("Exported", f"Saved to {os.path.basename(fp)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def export_pdf(self):
        if not self.results:
            messagebox.showwarning("Warning", "No results! Run scan first.")
            return
        if not REPORTLAB_OK:
            messagebox.showerror("Error", "PDF export requires reportlab.\nRun: pip install reportlab")
            return
        
        fp = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile="DR_Nilesh_Shah_Analysis.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not fp: return
        
        try:
            logo = pdf_logo(LOGO_PATH) if LOGO_PATH.exists() else None

            def add_header(canvas_obj, doc):
                canvas_obj.saveState()
                if logo:
                    try:
                        canvas_obj.drawImage(logo, 30, A4[1] - 80, width=50, height=50, preserveAspectRatio=True, mask='auto')
                    except: pass
                
                canvas_obj.setFont('Helvetica-Bold', 16)
                canvas_obj.setFillColor(colors.HexColor('#1f6feb'))
                canvas_obj.drawString(90, A4[1] - 55, "DR. NILESH SHAH'S MARKET ANALYSIS")
                
                canvas_obj.setStrokeColor(colors.HexColor('#1f6feb'))
                canvas_obj.setLineWidth(2)
                canvas_obj.line(30, A4[1] - 90, A4[0] - 30, A4[1] - 90)
                
                canvas_obj.setFont('Helvetica', 8)
                canvas_obj.setFillColor(colors.gray)
                canvas_obj.drawString(30, 30, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                canvas_obj.drawRightString(A4[0] - 30, 30, f"Page {doc.page}")
                canvas_obj.line(30, 45, A4[0] - 30, 45)
                canvas_obj.restoreState()
            
            doc = SimpleDocTemplate(fp, pagesize=A4, topMargin=100, bottomMargin=60, leftMargin=30, rightMargin=30)
            elements = []
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=14, spaceAfter=15, textColor=colors.HexColor('#1f6feb'))
            subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, spaceAfter=10, textColor=colors.gray)
            
            elements.append(Paragraph("Stock Technical Analysis Report", title_style))
            elements.append(Paragraph(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", subtitle_style))
            elements.append(Spacer(1, 15))
            
            total = len(self.results)
            sb = sum(1 for r in self.results if r['rec'] == 'STRONG BUY')
            buy = sum(1 for r in self.results if r['rec'] == 'BUY')
            hold = sum(1 for r in self.results if r['rec'] == 'HOLD')
            sell = sum(1 for r in self.results if r['rec'] == 'SELL')
            ss = sum(1 for r in self.results if r['rec'] == 'STRONG SELL')
            avg_score = sum(r['score'] for r in self.results) / total if total > 0 else 0
            
            summary_data = [
                ['Total Stocks', 'Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell', 'Avg Score'],
                [str(total), str(sb), str(buy), str(hold), str(sell), str(ss), f"{avg_score:.1f}"]
            ]
            
            t = Table(summary_data, colWidths=[80, 80, 60, 60, 60, 80, 70])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f6feb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, 1), 14),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 25))
            
            elements.append(Paragraph("Detailed Scan Results", ParagraphStyle('H', parent=styles['Heading2'], fontSize=12, spaceAfter=10)))
            
            table_data = [['Symbol', 'Price', 'Chg%', 'RSI', 'Score', 'Recommendation', 'SL', 'T1', 'T2', 'R:R']]
            
            for r in self.results:
                t = r.get('targets', {})
                rec = r['rec']
                
                if rec in ['STRONG BUY', 'BUY']:
                    rec_text = f'<font color="#059669"><b>{rec}</b></font>'
                elif rec in ['SELL', 'STRONG SELL']:
                    rec_text = f'<font color="#ef4444"><b>{rec}</b></font>'
                else:
                    rec_text = f'<font color="#d97706"><b>{rec}</b></font>'
                
                table_data.append([
                    r['symbol'] + ('*' if r.get('hourly') else ''), f"{r['price']:.2f}", f"{r['change']:+.2f}%",
                    f"{r['rsi']:.1f}", f"{r['score']:.1f}",
                    Paragraph(rec_text, styles['Normal']),
                    f"{t.get('sl', 'N/A')}", f"{t.get('t1', 'N/A')}", f"{t.get('t2', 'N/A')}",
                    f"1:{t.get('rr', 0)}"
                ])
            
            results_table = Table(table_data, colWidths=[55, 50, 45, 35, 40, 75, 50, 50, 50, 35])
            results_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f6feb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            ]))
            elements.append(results_table)
            if any(r.get('hourly') for r in self.results):
                elements.append(Spacer(1, 8))
                elements.append(Paragraph(market_data.HOURLY_NOTE, subtitle_style))

            doc.build(elements, onFirstPage=add_header, onLaterPages=add_header)
            messagebox.showinfo("PDF Exported", f"Report saved to:\n{os.path.basename(fp)}")
        except Exception as e:
            messagebox.showerror("Error", f"PDF export failed: {e}")
            logger.error(f"PDF export error: {e}")
    
    def view_log(self):
        log_path = LOG_FILE
        if not log_path.exists():
            messagebox.showinfo("Log", f"No log file found yet.\n{log_path}")
            return
        
        log_win = tk.Toplevel(self.root)
        log_win.title("Application Log")
        log_win.geometry("800x600")
        log_win.configure(bg=THEME['bg'])
        ui.set_titlebar(log_win, THEME['mode'] == 'dark')
        
        header = tk.Frame(log_win, bg=THEME['bg2'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=f"Application Log: {log_path}", bg=THEME['bg2'], fg=THEME['gold'],
                font=(ui.FONT, 11, 'bold')).pack(side=tk.LEFT, padx=15)
        
        text_frame = tk.Frame(log_win, bg=THEME['bg'])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        log_text = tk.Text(text_frame, bg=THEME['card'], fg=THEME['fg'], font=(ui.MONO, 10),
                          relief=tk.FLAT, highlightthickness=1, highlightbackground=THEME['line'], yscrollcommand=scrollbar.set)
        log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=log_text.yview)
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                log_text.insert(tk.END, f.read())
                log_text.see(tk.END)
        except Exception as e:
            log_text.insert(tk.END, f"Error: {e}")
        
        log_text.config(state=tk.DISABLED)
        
        btn_frame = tk.Frame(log_win, bg=THEME['bg'])
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def refresh():
            log_text.config(state=tk.NORMAL)
            log_text.delete(1.0, tk.END)
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    log_text.insert(tk.END, f.read())
                    log_text.see(tk.END)
            except: pass
            log_text.config(state=tk.DISABLED)
        
        self.btn(btn_frame, "Refresh", THEME['accent'], refresh).pack(side=tk.LEFT, padx=5)
        self.btn(btn_frame, "Close", THEME['bg3'], log_win.destroy).pack(side=tk.RIGHT, padx=5)
    
    def update_patterns(self, r):
        T = THEME
        for w in self.pt_frame.winfo_children():
            w.destroy()

        symbol = r['symbol']
        patterns = r.get('data', {}).get('patterns', {})

        tk.Label(self.pt_frame, text=f"Pattern Analysis: {symbol}",
                 bg=T['bg'], fg=T['fg'], font=(ui.DISPLAY, 18, 'bold')).pack(anchor=tk.W, padx=100, pady=(22, 12))

        summary = patterns.get('summary', {})
        total = summary.get('total_patterns', 0)
        bullish = summary.get('bullish_count', 0)
        bearish = summary.get('bearish_count', 0)
        overall = summary.get('overall_signal', 'N/A')

        stats_frame = tk.Frame(self.pt_frame, bg=T['bg'])
        stats_frame.pack(fill=tk.X, padx=100, pady=(0, 10))
        overall_c = T['buy'] if overall == 'BULLISH' else T['sell'] if overall == 'BEARISH' else T['warning']
        for i, (label, value, edge) in enumerate([("Total", str(total), T['accent']), ("Bullish", str(bullish), T['buy']),
                                                  ("Bearish", str(bearish), T['sell']), ("Overall", overall, overall_c)]):
            box = tk.Frame(stats_frame, bg=T['card'], highlightbackground=T['line'], highlightthickness=1)
            box.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0 if i == 0 else 5, 0))
            tk.Frame(box, bg=edge, height=3).pack(fill=tk.X)
            tk.Label(box, text=label, bg=T['card'], fg=T['fg2'], font=(ui.FONT, 9)).pack(pady=(8, 0))
            tk.Label(box, text=value, bg=T['card'], fg=T['fg'], font=(ui.DISPLAY, 18, 'bold')).pack(pady=(0, 8))

        ignored = summary.get('ignored_conflicts') or []
        if ignored:
            tk.Label(self.pt_frame, text=f"Ignored conflicting pattern(s): {', '.join(ignored)} - a stronger or more recent "
                                         f"pattern points the other way",
                     bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 9, 'italic')).pack(anchor=tk.W, padx=100, pady=(0, 5))

        def badge(parent, signal):
            bg, fg = {'BULLISH': (T['reward_bg'], T['reward_fg']), 'BEARISH': (T['risk_bg'], T['risk_fg'])}.get(
                signal, (T['warn_bg'], T['warn_fg']))
            tk.Label(parent, text=signal.capitalize() if signal else '', bg=bg, fg=fg, font=(ui.FONT, 9, 'bold'),
                     padx=10, pady=2).pack(side=tk.LEFT, padx=10)

        def section(title, items, empty, long_text):
            if not items:
                tk.Label(self.pt_frame, text=empty, bg=T['bg'], fg=T['fg3'], font=(ui.FONT, 11)).pack(anchor=tk.W, padx=100, pady=8)
                return
            box = tk.Frame(self.pt_frame, bg=T['card'], highlightbackground=T['line'], highlightthickness=1)
            box.pack(fill=tk.X, padx=100, pady=(4, 10))
            tk.Label(box, text=title, bg=T['card'], fg=T['fg2'], font=(ui.FONT, 10, 'bold')).pack(anchor=tk.W, padx=18, pady=(12, 4))
            for n, pattern in enumerate(items):
                if n:
                    tk.Frame(box, bg=T['line'], height=1).pack(fill=tk.X, padx=18)
                row = tk.Frame(box, bg=T['card'])
                row.pack(fill=tk.X, padx=18, pady=8)
                head = tk.Frame(row, bg=T['card'])
                head.pack(fill=tk.X)
                tk.Label(head, text=pattern.get('name', ''), bg=T['card'], fg=T['fg'], font=(ui.FONT, 11, 'bold')).pack(side=tk.LEFT)
                badge(head, pattern.get('signal', ''))
                if long_text and pattern.get('description'):
                    tk.Label(row, text=pattern['description'], bg=T['card'], fg=T['fg3'], font=(ui.FONT, 10),
                             wraplength=700, justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 0))
            tk.Frame(box, bg=T['card'], height=4).pack()

        section("Chart patterns", patterns.get('chart', []), "No chart patterns detected", True)
        section("Candlestick patterns", patterns.get('candlestick', []), "No candlestick patterns detected", False)
        # Harmonic patterns are included in the counts above, so list them too
        if patterns.get('harmonic'):
            section("Harmonic patterns", patterns['harmonic'], "", True)

        self.nb.select(4)

    def sort_tree(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        
        def num(text):   # leading number of a cell, e.g. '+1.25%' -> 1.25, '0.42 LOW' -> 0.42
            m = re.match(r'\s*([+-]?\d+(?:\.\d+)?)', str(text).replace(',', ''))
            return float(m.group(1)) if m else None

        if not hasattr(self, '_sort_col') or self._sort_col != col:
            self._sort_asc = True
            self._sort_col = col
        else:
            self._sort_asc = not self._sort_asc

        numbered = [(num(v), v, k) for v, k in items]
        if sum(n is not None for n, _, _ in numbered) >= max(1, len(numbered) // 2):
            # mostly numbers: sort numerically, and keep text cells ('N/A', 'new') at the bottom
            # in both directions (one 'N/A' used to make the whole column sort as text)
            ordered = sorted([x for x in numbered if x[0] is not None], key=lambda x: x[0], reverse=not self._sort_asc)
            ordered += [x for x in numbered if x[0] is None]
        else:
            ordered = sorted(numbered, key=lambda x: str(x[1]), reverse=not self._sort_asc)
        for index, (_, _, k) in enumerate(ordered):
            self.tree.move(k, '', index)
        self._restripe()
    
    def start_scan(self):
        if not self.watchlist:
            messagebox.showwarning("Warning", "Add stocks first!")
            return
        if self.scanning: return
        self.scanning = True
        self.scan_btn.configure(state=tk.DISABLED, text="Scanning...")
        self.results = []
        self.tree.delete(*self.tree.get_children())
        threading.Thread(target=self._scan, daemon=True).start()
    
    def _scan(self):
        watchlist = list(self.watchlist)
        total = len(watchlist)
        failed = []
        too_new = []   # listed a day or two ago: not enough 1-hour candles to score yet
        t0 = time.time()
        
        # 1. Download every stock's prices in one batch (disk-cached; re-scans only fetch recent days)
        self.gui.schedule(self._status, f"Downloading prices for {total} stocks...", 2)
        try:
            frames = self.analyzer.fetch_many(
                watchlist, progress=lambda msg: self.gui.schedule(self._status, msg, 5))
        except Exception as e:
            logger.error(f"Batch download failed: {e}")
            frames = {}

        # Nifty 50, for each stock's relative strength
        nifty = None
        if MARKET_DATA_OK:
            try:
                nifty = market_data.load_history([NIFTY_SYMBOL], years=HISTORY_YEARS, exchange='INDEX').get(NIFTY_SYMBOL)
            except Exception as e:
                logger.warning(f"Nifty 50 download failed (relative strength not shown): {e}")

        # 2. Analyse each stock (CPU only - no network)
        for i, sym in enumerate(watchlist):
            self.gui.schedule(self._status, f"Analysing {sym} ({i+1}/{total})...", 10 + (i / total) * 90)
            df = frames.get(sym)
            if df is None or df.empty:
                self.gui.schedule(self._add_error, sym, "No data / delisted")
                failed.append(sym)
                continue
            if len(df) < 20:   # only a new listing's 1-hour candles come this short
                self.gui.schedule(self._add_error, sym, "Listed under 3 days ago")
                too_new.append(sym)
                continue
            try:
                days = self.analyzer.listing_days.get(sym)   # None unless it's a new listing
                data = self.analyzer.analyze(df, days=days)
                score = self.scorer.score(data)
                change = ((data['price'] - data['prev']) / data['prev'] * 100) if data['prev'] > 0 else 0
                targets = TargetCalc.calc(data, score['rec'])

                # 52-week high/low (df holds 2 years, so use the last year only)
                last_year = df[df.index > df.index[-1] - pd.DateOffset(weeks=52)]
                high52 = float(last_year['High'].max()) if len(last_year) > 0 else data['price']
                low52 = float(last_year['Low'].min()) if len(last_year) > 0 else data['price']

                result = {
                    'symbol': sym, 'price': data['price'], 'change': change,
                    'rsi': data['rsi'], 'score': score['total'], 'rec': score['rec'],
                    'breakdown': score['breakdown'], 'data': data, 'targets': targets,
                    'st_sig': data['supertrend']['sig'], 'st_dir': data['supertrend']['dir'],
                    'vwap_sig': data['vwap']['sig'],
                    'patterns': data.get('patterns', {}),
                    'high52': high52, 'low52': low52,
                    # vs the Nifty: periods are in trading days, which a new listing doesn't have yet (N/A)
                    'rs': relative_strength(df if days is None else days, nifty),
                    'hourly': data['hourly']
                }
                self.results.append(result)
                self.gui.schedule(self._add_tree, result)
            except Exception as e:
                logger.error(f"Scan {sym}: {e}")
                self.gui.schedule(self._add_error, sym, str(e)[:30])
                failed.append(sym)
        
        logger.info(f"Scan: {total - len(failed) - len(too_new)}/{total} stocks in {time.time() - t0:.1f}s")
        self.results.sort(key=lambda x: x['symbol'])

        # 3. Compare with the previous scan day, then save this scan to the score history
        changes = []
        if HISTORY_OK and self.results:
            try:
                prev = score_history.previous([r['symbol'] for r in self.results])
                for r in self.results:
                    p = prev.get(r['symbol'])
                    if p and p.get('score'):
                        r['prev_score'], r['prev_rec'], r['prev_date'] = float(p['score']), p['rec'], p['date']
                        if p['rec'] != r['rec']:
                            changes.append(f"{r['symbol']}: {p['rec']} -> {r['rec']}  (since {p['date']})")
                score_history.record(self.results)
            except Exception as e:
                logger.error(f"Score history: {e}")
        self.gui.schedule(self._scan_done, failed, changes, too_new)
    
    def _status(self, msg, pct):
        self.status_lbl.configure(text=msg)
        self.progress['value'] = pct
    
    def _row_tag(self, rec, index):
        """Row look: buy and sell rows lightly tinted, hold rows striped."""
        if 'BUY' in rec:
            return 'tb'
        if 'SELL' in rec:
            return 'ts'
        return 'zebra' if index % 2 else 'plain'

    def _add_tree(self, r):
        """One results row. The signal shows as a marker shape (not colour alone) in the first column."""
        data = r.get('data', {})
        high52 = r.get('high52', 0)
        low52 = r.get('low52', 0)
        atr = safe_float(data.get('atr', 0))
        liq = self._liquidity_text(r)
        rs3 = (r.get('rs') or {}).get('3M')
        rs_text = f"{rs3:+.1f}%" if rs3 is not None else "N/A"
        chg_text = f"{r['score'] - r['prev_score']:+.1f}" if r.get('prev_score') is not None else "new"
        index = len(self.tree.get_children())
        self.tree.insert('', tk.END, text='', image=self.markers.get(r['rec'], self.markers['ERROR']), values=(
            r['symbol'], f"{r['price']:,.2f}", f"{r['change']:+.2f}%", rs_text,
            f"{r['rsi']:.1f}", r.get('st_sig', ''), r.get('vwap_sig', ''),
            f"{r['score']:.1f}", chg_text, r['rec'],
            f"{high52:,.2f}", f"{low52:,.2f}", f"{atr:.2f}", liq,
            '1 Hour' if r.get('hourly') else 'Daily'
        ), tags=(self._row_tag(r['rec'], index),))

    def _restripe(self):
        """Stripes follow the rows' order again (after sorting or filtering)."""
        for i, item in enumerate(self.tree.get_children()):
            tags = self.tree.item(item, 'tags')
            if tags and tags[0] in ('zebra', 'plain'):
                self.tree.item(item, tags=('zebra' if i % 2 else 'plain',))

    def _flash_changes(self):
        """Rows whose signal changed since the last scan glow once and settle, so they stand out."""
        T = THEME
        by_symbol = {r['symbol']: r for r in self.results}
        k = 0
        for i, item in enumerate(self.tree.get_children()):
            r = by_symbol.get(str(self.tree.item(item)['values'][0]))
            if not r or not r.get('prev_rec') or r['prev_rec'] == r['rec']:
                continue
            base_tag = self._row_tag(r['rec'], i)
            base = {'tb': T['tint_b'], 'ts': T['tint_s'], 'zebra': T['zebra'], 'plain': T['card']}[base_tag]
            tag = f'flash{k}'
            k += 1
            self.tree.item(item, tags=(tag,))

            def step(v, tag=tag, base=base):
                self.tree.tag_configure(tag, background=ui.blend(T['flash'], base, v))

            def done(item=item, base_tag=base_tag):
                if self.tree.exists(item):
                    self.tree.item(item, tags=(base_tag,))
            self.tree.tag_configure(tag, background=T['flash'])
            self.root.after(250, lambda step=step, done=done: ui.tween(self.tree, 1800, step, done=done, ease=ui.ease_in_out))

    def toast(self, title, message='', kind='info', ms=6000):
        """A message that slides up in the corner and leaves by itself (ui.Toast)."""
        self.last_toast = (title, message)
        ui.Toast(self.root, title, message, THEME, ms=ms, kind=kind)

    def _scan_done(self, failed=None, changes=None, too_new=None):
        self.scanning = False
        self.scan_btn.configure(state=tk.NORMAL, text="Scan all stocks")
        self.progress['value'] = 100
        self.status_lbl.configure(text="Complete")

        self.results.sort(key=lambda x: x['symbol'])
        self.tree.delete(*self.tree.get_children())
        for r in self.results:
            self._add_tree(r)

        self._all_results = self.results.copy()
        self._last_scan_at = datetime.now()

        self.nb.select(1)
        self.update_dash()
        self.last_scan_lbl.configure(text=f"Last scan: {self._last_scan_at:%H:%M:%S}")
        self.cache_lbl.configure(text=f"Cache: {self.analyzer.cache.count()}")   # it used to stay at 0 forever
        self._flash_changes()

        # The result slides in at the corner instead of a box that has to be closed
        lines = []
        if failed:
            lines.append(f"{len(failed)} failed: {', '.join(failed[:5])}")
        if too_new:
            lines.append(f"{len(too_new)} listed under 3 trading days ago: {', '.join(too_new[:5])} "
                         "(a new listing is scored from its 3rd day, on 1-hour candles)")
        if changes:
            shown = [c.split('  (since')[0].replace(' -> ', ' to ') for c in changes[:4]]
            line = f"Signal changes since the last scan ({len(changes)}): " + "; ".join(shown)
            if len(changes) > 4:
                line += f"; and {len(changes) - 4} more (see the 'Score Chg' column)"
            lines.append(line)
        self.toast(f"Scan complete: {len(self.results)} stocks", "\n".join(lines) or "No signal changes since your last scan.",
                   kind='warn' if failed else 'good', ms=10000 if changes or failed else 6000)

    def _add_error(self, symbol, error):
        """Add error entry to tree."""
        values = [symbol] + ['N/A'] * (len(self.tree['columns']) - 1)
        values[list(self.tree['columns']).index('Recommendation')] = f'Error: {error}'
        self.tree.insert('', tk.END, image=self.markers['ERROR'], values=values, tags=('error',))

    def filter_results(self):
        """Filter results based on search and recommendation filter."""
        search = self.search_var.get().upper()
        rec_filter = self.result_filter_var.get()

        if not hasattr(self, '_all_results'):
            self._all_results = self.results.copy()

        for item in self.tree.get_children():
            self.tree.delete(item)

        for r in self._all_results:
            if search and search not in r['symbol'].upper():
                continue
            if rec_filter != "All" and r['rec'] != rec_filter:
                continue
            if self.hide_illiquid_var.get() and self._is_illiquid(r):
                continue
            self._add_tree(r)

    def _is_illiquid(self, r):
        return r.get('data', {}).get('liquidity_cr', 0) < self.min_liquidity_cr

    def _liquidity_text(self, r):
        liq = r.get('data', {}).get('liquidity_cr', 0)
        text = f"{liq:,.2f}" if liq < 100 else f"{liq:,.0f}"
        return f"{text}  LOW" if self._is_illiquid(r) else text

    def update_dash(self, animate=True):
        """The summary card: numbers count up and the buy / hold / sell bar grows."""
        if not self.results: return
        counts = {k: sum(1 for r in self.results if r['rec'] == k) for k in ('STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL')}
        avg = sum(r['score'] for r in self.results) / len(self.results)
        when = getattr(self, '_last_scan_at', None)
        self.summary.update_values(counts, len(self.results), avg, f"Last scan at {when:%H:%M}" if when else '', animate)

    def show_details(self, event):
        sel = self.tree.selection()
        if not sel: return
        sym = str(self.tree.item(sel[0])['values'][0])  # Treeview turns numeric symbols (BSE codes) into int
        r = next((x for x in self.results if x['symbol'] == sym), None)
        if not r: return
        self._detail_symbol = sym
        self.update_breakdown(r)
        self.update_targets(r)
        self.update_patterns(r)
        self.nb.select(2)
    
    def update_breakdown(self, r):
        T = THEME
        for w in self.bd_frame.winfo_children():
            w.destroy()

        score, rec = r['score'], r['rec']
        color = ui.signal_color(T, rec)

        tk.Label(self.bd_frame, text=f"Score Breakdown: {r['symbol']}",
                 bg=T['bg'], fg=T['fg'], font=(ui.DISPLAY, 18, 'bold')).pack(anchor=tk.W, padx=100, pady=(22, 12))

        # The score: a ring that sweeps round to it, with the facts beside it
        top = tk.Frame(self.bd_frame, bg=T['card'], highlightbackground=T['line'], highlightthickness=1)
        top.pack(fill=tk.X, padx=100, pady=(0, 10))
        ring = ui.ScoreRing(top, T)
        ring.pack(side=tk.LEFT, padx=18, pady=14)
        ring.show(score, color, rec)
        info = tk.Frame(top, bg=T['card'])
        info.pack(side=tk.LEFT, fill=tk.X, padx=(4, 18))
        tk.Label(info, text=rec, bg=T['card'], fg=T['fg'], font=(ui.DISPLAY, 20, 'bold')).pack(anchor=tk.W)
        tk.Label(info, text=f"Price {r['price']:,.2f}, {r['change']:+.2f}% on the day",
                 bg=T['card'], fg=T['fg2'], font=(ui.FONT, 12)).pack(anchor=tk.W, pady=(2, 8))

        # Relative strength: did the stock beat the Nifty 50?
        rs = r.get('rs') or {}
        if any(v is not None for v in rs.values()):
            rs_row = tk.Frame(info, bg=T['card'])
            rs_row.pack(anchor=tk.W)
            tk.Label(rs_row, text="vs Nifty 50:", bg=T['card'], fg=T['fg2'], font=(ui.FONT, 11)).pack(side=tk.LEFT, padx=(0, 4))
            for label, v in rs.items():
                text = f"{label} {v:+.1f}%" if v is not None else f"{label} N/A"
                fg = T['fg3'] if v is None else T['success'] if v > 0 else T['danger2'] if v < 0 else T['fg']
                tk.Label(rs_row, text=text, bg=T['card'], fg=fg, font=(ui.FONT, 11, 'bold')).pack(side=tk.LEFT, padx=8)
            rs3 = rs.get('3M')
            if rs3 is not None:
                verdict = "beating" if rs3 > 0 else "lagging"
                tk.Label(info, text=f"Over 3 months the stock is {verdict} the market by {abs(rs3):.1f} percentage points.",
                         bg=T['card'], fg=T['fg3'], font=(ui.FONT, 10)).pack(anchor=tk.W, pady=(6, 0))
        if r.get('hourly'):
            tk.Label(self.bd_frame, text=f"New listing ({r['data']['days']} trading days of history): "
                                         "analysed on 1-hour candles instead of daily ones.",
                     bg=T['info_bg'], fg=T['info_fg'], font=(ui.FONT, 10, 'bold'), padx=12, pady=8,
                     anchor=tk.W).pack(fill=tk.X, padx=100, pady=(0, 10))

        # What makes up the score: bars that grow one after another
        names = {'rsi': 'RSI', 'macd': 'MACD', 'ma': 'Moving Avg', 'boll': 'Bollinger',
                 'stoch': 'Stochastic', 'adx': 'ADX', 'vol': 'Volume', 'mom': 'Momentum',
                 'st': 'SuperTrend', 'vwap': 'VWAP'}
        card = tk.Frame(self.bd_frame, bg=T['card'], highlightbackground=T['line'], highlightthickness=1)
        card.pack(fill=tk.X, padx=100, pady=(0, 10))
        tk.Label(card, text="What makes up the score (each part 0 to 100)", bg=T['card'], fg=T['fg2'],
                 font=(ui.FONT, 10, 'bold')).pack(anchor=tk.W, padx=18, pady=(12, 6))
        bar_w = 380
        for i, (key, val) in enumerate(r['breakdown'].items()):
            row = tk.Frame(card, bg=T['card'])
            row.pack(fill=tk.X, padx=18, pady=3)
            tk.Label(row, text=names.get(key, key), bg=T['card'], fg=T['fg'],
                     font=(ui.FONT, 11), width=14, anchor=tk.W).pack(side=tk.LEFT)
            c = T['sb'] if val >= 70 else T['buy'] if val >= 50 else T['hold'] if val >= 30 else T['sell']
            bar = tk.Canvas(row, width=bar_w, height=14, bg=T['card'], highlightthickness=0)
            bar.pack(side=tk.LEFT, padx=8)
            ui.round_rect(bar, 0, 2, bar_w, 12, 5, fill=T['bg3'], outline='')

            def grow(v, bar=bar, val=val, c=c):
                bar.delete('fill')
                w = bar_w * val / 100 * v
                if w > 1:
                    ui.round_rect(bar, 0, 2, w, 12, 5, fill=c, outline='', tags='fill')
            self.root.after(i * 45, lambda grow=grow, bar=bar: ui.tween(bar, 700, grow))
            tk.Label(row, text=f"{val}", bg=T['card'], fg=T['fg'], font=(ui.DISPLAY, 11, 'bold'), width=4,
                     anchor=tk.E).pack(side=tk.LEFT)
            lbl = "Strong" if val >= 70 else "Good" if val >= 50 else "Weak" if val >= 30 else "Bearish"
            tk.Label(row, text=lbl, bg=T['card'], fg=T['fg2'], font=(ui.FONT, 10), width=8, anchor=tk.W).pack(side=tk.LEFT, padx=(8, 0))
        tk.Frame(card, bg=T['card'], height=8).pack()

        self._draw_score_history(r)

    def _draw_score_history(self, r):
        """Score history chart (one point per scan day) under the breakdown."""
        if not HISTORY_OK:
            return
        T = THEME
        try:
            hist = score_history.history(r['symbol'])
        except Exception as e:
            logger.error(f"Score history read failed: {e}")
            return
        box = tk.Frame(self.bd_frame, bg=T['card'], highlightbackground=T['line'], highlightthickness=1)
        box.pack(fill=tk.X, padx=100, pady=(0, 16))
        tk.Label(box, text="Score history", bg=T['card'], fg=T['fg2'],
                 font=(ui.FONT, 10, 'bold')).pack(anchor=tk.W, padx=18, pady=(12, 4))
        if len(hist) < 2 or not MATPLOTLIB_OK:
            tk.Label(box, text="The history builds up as you scan on different days - one point per day.",
                     bg=T['card'], fg=T['fg3'], font=(ui.FONT, 10)).pack(anchor=tk.W, padx=18, pady=(0, 12))
            return
        dates = [datetime.strptime(h['date'], '%Y-%m-%d') for h in hist]
        scores = [safe_float(h['score']) for h in hist]
        fig = Figure(figsize=(9, 2.6), dpi=100, facecolor=T['card'], layout='constrained')
        ax = fig.add_subplot(111)
        self._style_axes(ax)
        for level, col in ((75, T['sb']), (60, T['buy']), (45, T['hold']), (30, T['sell'])):
            ax.axhline(level, color=col, linewidth=0.9, linestyle='--', alpha=1.0)
        ax.plot(dates, scores, color=T['series0'], linewidth=2, marker='o', markersize=4)
        ax.set_ylim(0, 100)
        ax.set_ylabel('Score', color=T['chart_fg'], fontsize=9)
        fig.autofmt_xdate()
        chart = FigureCanvasTkAgg(fig, master=box)
        chart.draw()
        chart.get_tk_widget().pack(fill=tk.X, padx=5, pady=5)
        first, last = hist[0], hist[-1]
        tk.Label(box, text=f"{len(hist)} scan days | first {first['date']}: {safe_float(first['score']):.1f} ({first['rec']})  ->  "
                           f"latest {last['date']}: {safe_float(last['score']):.1f} ({last['rec']})   "
                           f"(dashed lines: 75 Strong Buy, 60 Buy, 45 Hold, 30 Sell)",
                 bg=T['card'], fg=T['fg3'], font=(ui.FONT, 9)).pack(pady=(0, 10))

    def _style_axes(self, ax):
        """Chart axes in the theme's colours: quiet grid and labels, no heavy frame."""
        T = THEME
        ax.set_facecolor(T['chart_bg'])
        ax.tick_params(colors=T['chart_fg'], labelsize=8)
        for side in ax.spines.values():
            side.set_color(T['chart_grid'])
        ax.grid(True, color=T['chart_grid'], linewidth=0.6)
        ax.set_axisbelow(True)

    def _panel(self, parent, edge=None, **pack):
        """A white (dark: raised) card with a thin border; `edge` adds a coloured strip on its left."""
        T = THEME
        outer = tk.Frame(parent, bg=T['card'], highlightbackground=T['line'], highlightthickness=1)
        outer.pack(fill=tk.X, padx=100, **pack)
        if edge:
            tk.Frame(outer, bg=edge, width=4).pack(side=tk.LEFT, fill=tk.Y)
        body = tk.Frame(outer, bg=T['card'])
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return body

    def _price_ladder(self, parent, price, levels):
        """The stop-loss, price and targets on one line, to scale. The marks slide out from
        the price to where they sit, so you see at a glance how far each level is."""
        T = THEME
        pts = [(lbl, v, c) for lbl, v, c in levels if v]
        if not pts or not price:
            return
        lo = min([price] + [v for _, v, _ in pts])
        hi = max([price] + [v for _, v, _ in pts])
        span = (hi - lo) or price * 0.01 or 1
        cv = tk.Canvas(parent, height=96, bg=T['card'], highlightthickness=0)
        cv.pack(fill=tk.X, padx=18, pady=(4, 12))

        def draw(v):
            cv.delete('all')
            w = cv.winfo_width()
            if w < 100:
                return
            x0, x1 = 40, w - 40
            pos = lambda val: x0 + (val - lo) / span * (x1 - x0)
            y = 40
            ui.round_rect(cv, x0 - 6, y - 3, x1 + 6, y + 3, 3, fill=T['bg3'], outline='')
            px = pos(price)
            for lbl, val, c in sorted(pts, key=lambda p: -abs(p[1] - price)):    # nearer levels drawn on top
                cv.create_line(px, y, px + (pos(val) - px) * v, y, fill=c, width=3)
            for i, (lbl, val, c) in enumerate(sorted(pts, key=lambda p: p[1])):
                x = px + (pos(val) - px) * v
                cv.create_oval(x - 7, y - 7, x + 7, y + 7, fill=c, outline=T['card'], width=2)
                up = i % 2 == 0
                cv.create_text(x, y - 16 if up else y + 18, text=lbl, fill=T['fg2'], font=(ui.FONT, 9),
                               anchor='s' if up else 'n')
                cv.create_text(x, y - 28 if up else y + 32, text=f"{val:,.2f}", fill=T['fg'], font=(ui.FONT, 9, 'bold'),
                               anchor='s' if up else 'n')
            cv.create_rectangle(px - 2, y - 13, px + 2, y + 13, fill=T['fg'], outline='')
            cv.create_text(px, y + 30, text=f"Price {price:,.2f}", fill=T['fg'], font=(ui.FONT, 9, 'bold'))

        cv.bind('<Configure>', lambda e: draw(1.0))
        self.root.after(80, lambda: ui.tween(cv, 800, draw))

    def update_targets(self, r):
        T = THEME
        for w in self.tg_frame.winfo_children():
            w.destroy()

        t = r.get('targets', {})
        if not t:
            tk.Label(self.tg_frame, text="No target data", bg=T['bg'], fg=T['fg3']).pack(pady=50)
            return

        price = t.get('price', 0)
        rec = r['rec']

        tk.Label(self.tg_frame, text=f"Stop-Loss & Targets: {r['symbol']}",
                 bg=T['bg'], fg=T['fg'], font=(ui.DISPLAY, 18, 'bold')).pack(anchor=tk.W, padx=100, pady=(22, 12))

        head = self._panel(self.tg_frame, edge=ui.signal_color(T, rec), pady=(0, 10))
        tk.Label(head, text=f"{price:,.2f}", bg=T['card'], fg=T['fg'], font=(ui.DISPLAY, 28, 'bold')).pack(anchor=tk.W, padx=18, pady=(12, 0))
        tk.Label(head, text=f"{rec}   |   Position: {t.get('pos', '')}", bg=T['card'], fg=T['fg2'],
                 font=(ui.FONT, 12, 'bold')).pack(anchor=tk.W, padx=18, pady=(0, 12))

        if self._is_illiquid(r):
            liq = r.get('data', {}).get('liquidity_cr', 0)
            tk.Label(self.tg_frame, text=f"Low liquidity: only about Rs {liq:.2f} crore traded per day "
                                         f"(threshold Rs {self.min_liquidity_cr:g} Cr).\n"
                                         "Price can gap past the stop-loss and orders may not fill - treat these levels with caution.",
                     bg=T['warn_bg'], fg=T['warn_fg'], font=(ui.FONT, 10, 'bold'), padx=12, pady=8,
                     justify=tk.LEFT, anchor=tk.W).pack(fill=tk.X, padx=100, pady=(0, 10))

        if r.get('hourly'):
            tk.Label(self.tg_frame, text="New listing, 1-hour candles: the stop-loss and targets come from hourly price swings,\n"
                                         "so they sit closer to the price than for stocks analysed on daily candles.",
                     bg=T['info_bg'], fg=T['info_fg'], font=(ui.FONT, 10, 'bold'), padx=12, pady=8,
                     justify=tk.LEFT, anchor=tk.W).pack(fill=tk.X, padx=100, pady=(0, 10))

        # Each level says where it comes from: the stock's own support/resistance, or the ATR
        basis = t.get('basis', {})
        def why(key, text):
            return f"{text}  |  {basis[key][0].upper()}{basis[key][1:]}" if basis.get(key) else text
        stop_text = 'Exit if price rises above' if t.get('pos') == 'SHORT' else 'Exit if price falls below'
        levels = [
            ("STOP LOSS", t.get('sl', 0), T['sell'], why('sl', stop_text)),
            ("TARGET 1 (Conservative)", t.get('t1', 0), T['buy'], why('t1', 'Book partial profits')),
            ("TARGET 2 (Moderate)", t.get('t2', 0), T['sb'], why('t2', 'Main target - book 50%')),
            ("TARGET 3 (Aggressive)", t.get('t3', 0), T['accent'], why('t3', 'Trail stop loss')),
        ]

        ladder = self._panel(self.tg_frame, pady=(0, 10))
        tk.Label(ladder, text="Where the levels sit", bg=T['card'], fg=T['fg2'],
                 font=(ui.FONT, 10, 'bold')).pack(anchor=tk.W, padx=18, pady=(12, 0))
        self._price_ladder(ladder, price, [("Stop", t.get('sl', 0), T['sell']), ("T1", t.get('t1', 0), T['buy']),
                                           ("T2", t.get('t2', 0), T['sb']), ("T3", t.get('t3', 0), T['accent'])])

        grid = tk.Frame(self.tg_frame, bg=T['bg'])
        grid.pack(fill=tk.X, padx=100, pady=(0, 4))
        for i, (label, val, color, desc) in enumerate(levels):
            grid.columnconfigure(i % 2, weight=1, uniform='lv')
            outer = tk.Frame(grid, bg=T['card'], highlightbackground=T['line'], highlightthickness=1)
            outer.grid(row=i // 2, column=i % 2, sticky='nsew', padx=(0 if i % 2 == 0 else 5, 5 if i % 2 == 0 else 0), pady=5)
            tk.Frame(outer, bg=color, width=4).pack(side=tk.LEFT, fill=tk.Y)
            body = tk.Frame(outer, bg=T['card'])
            body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tk.Label(body, text=label, bg=T['card'], fg=T['fg2'], font=(ui.FONT, 10, 'bold')).pack(anchor=tk.W, padx=15, pady=(10, 0))
            tk.Label(body, text=f"{val:,.2f}" if val else "N/A", bg=T['card'], fg=T['fg'], font=(ui.DISPLAY, 22, 'bold')).pack(anchor=tk.W, padx=15, pady=2)
            tk.Label(body, text=desc, bg=T['card'], fg=T['fg3'], font=(ui.FONT, 9), wraplength=420,
                     justify=tk.LEFT).pack(anchor=tk.W, padx=15, pady=(0, 10))

        # Risk-Reward
        rr_frame = self._panel(self.tg_frame, pady=10)
        tk.Label(rr_frame, text="Risk-reward", bg=T['card'], fg=T['fg'], font=(ui.DISPLAY, 14, 'bold')).pack(anchor=tk.W, padx=18, pady=(14, 6))

        risk_amt = t.get('risk', 0) or 0
        reward_amt = t.get('reward', 0) or 0
        rr = t.get('rr', 0) or 0

        boxes = tk.Frame(rr_frame, bg=T['card'])
        boxes.pack(fill=tk.X, padx=18, pady=6)
        for title, amt, bg, fg in (("Risk", risk_amt, T['risk_bg'], T['risk_fg']), (None, None, None, None),
                                   ("Reward", reward_amt, T['reward_bg'], T['reward_fg'])):
            if title is None:
                tk.Label(boxes, text="->", bg=T['card'], fg=T['fg3'], font=(ui.FONT, 20, 'bold')).pack(side=tk.LEFT, padx=12)
                continue
            box = tk.Frame(boxes, bg=bg)
            box.pack(side=tk.LEFT, expand=True, fill=tk.X)
            tk.Label(box, text=title, bg=bg, fg=fg, font=(ui.FONT, 10, 'bold')).pack(pady=(10, 2))
            tk.Label(box, text=f"{amt:,.2f}", bg=bg, fg=T['fg'], font=(ui.DISPLAY, 22, 'bold')).pack(pady=2)
            tk.Label(box, text=f"{(amt/price*100):.1f}% of the price" if price > 0 else "", bg=bg, fg=fg,
                     font=(ui.FONT, 10)).pack(pady=(0, 10))

        # Ratio
        rr_c = T['sb'] if rr >= 2 else T['success'] if rr >= 1.5 else T['warning'] if rr >= 1 else T['danger2']
        quality = "Excellent" if rr >= 2 else "Good" if rr >= 1.5 else "Acceptable" if rr >= 1 else "Poor"

        tk.Label(rr_frame, text="Risk : Reward", bg=T['card'], fg=T['fg3'], font=(ui.FONT, 11)).pack(pady=(12, 0))
        tk.Label(rr_frame, text=f"1 : {rr:.2f}" if rr > 0 else "N/A", bg=T['card'], fg=rr_c, font=(ui.DISPLAY, 34, 'bold')).pack()
        tk.Label(rr_frame, text=f"Quality: {quality}", bg=T['card'], fg=rr_c, font=(ui.FONT, 13, 'bold')).pack(pady=(0, 6))
        main_target = "Target 1" if t.get('pos') == 'HOLD' else "Target 2"
        tk.Label(rr_frame, text=f"Risk = from the price to the stop-loss.  Reward = from the price to {main_target}.\n"
                                "The levels are this stock's own support and resistance, so the ratio differs from stock to stock.",
                 bg=T['card'], fg=T['fg3'], font=(ui.FONT, 9)).pack(pady=(0, 14))

        # Advice
        advice_f = self._panel(self.tg_frame, edge=T['warning'], pady=(4, 20))
        tk.Label(advice_f, text="Trading advice", bg=T['card'], fg=T['fg'], font=(ui.DISPLAY, 12, 'bold')).pack(anchor=tk.W, padx=18, pady=(12, 4))

        if rec in ['STRONG BUY', 'BUY']:
            advice = f"Enter at: {price:,.2f}\nStop Loss: {t.get('sl', 0):,.2f}\nTarget: {t.get('t1', 0):,.2f}\nRisk: {(risk_amt/price*100):.1f}% per trade"
        elif rec in ['SELL', 'STRONG SELL']:
            advice = f"Exit at: {price:,.2f}\nStop Loss: {t.get('sl', 0):,.2f}\nTarget: {t.get('t1', 0):,.2f}"
        else:
            advice = f"Support: {t.get('sl', 0):,.2f}\nResistance: {t.get('t1', 0):,.2f}\nWait for breakout"

        tk.Label(advice_f, text=advice, bg=T['card'], fg=T['fg'], font=(ui.FONT, 11), justify=tk.LEFT).pack(anchor=tk.W, padx=18, pady=(0, 14))

        self.nb.select(3)

    def generate_daily_report(self):
        if not REPORT_OK:
            messagebox.showerror("Error", "Daily report module not found.")
            return
        
        result = messagebox.askyesnocancel("Daily Report",
            "Generate Daily Market Report?\n\nYes = Indian + US Markets\nNo = Indian Market Only\nCancel = Cancel")
        
        if result is None: return
        
        include_us = result
        watchlist = list(self.watchlist)
        self.status_lbl.configure(text="Generating daily report (this can take a few minutes)...")

        # Analysing ~130 stocks takes minutes - run in the background so the window doesn't freeze
        def work():
            try:
                generator = DailyReportGenerator()
                report = generator.generate_report(watchlist={'NSE': watchlist}, include_us=include_us, include_india=True)
                pdf_path = generator.generate_pdf_report(report)

                summary = report.get('summary', {})
                wl = report.get('sections', {}).get('watchlist', {})
                msg = (f"Daily Report Generated!\n\n"
                       f"Watchlist stocks: {wl.get('total', 0)}\n"
                       f"Market stocks: {summary.get('total_stocks', 0)}\n"
                       f"Buy: {summary.get('strong_buy', 0) + summary.get('buy', 0)}\n"
                       f"Hold: {summary.get('hold', 0)}\n"
                       f"Sell: {summary.get('sell', 0) + summary.get('strong_sell', 0)}\n"
                       f"Avg Score: {summary.get('avg_score', 0)}\n"
                       f"PDF: {pdf_path}")

                self.root.after(0, lambda: messagebox.showinfo("Report Generated", msg))
                self.root.after(0, lambda: self.status_lbl.configure(text="Daily report generated!"))
            except Exception as e:
                logger.error(f"Daily report error: {e}")
                self.root.after(0, lambda: self.status_lbl.configure(text="Report failed"))
                self.root.after(0, lambda err=e: messagebox.showerror("Error", f"Report generation failed: {err}"))

        threading.Thread(target=work, daemon=True).start()
    
    def send_email_report(self):
        """Send report via email - gives user choice between watchlist or full market report."""
        if not REPORT_OK:
            messagebox.showerror("Error", "Daily report module not found.")
            return
        
        try:
            from daily_report import EmailConfig
            
            email_config = EmailConfig()
            
            if not email_config.is_configured:
                messagebox.showinfo("Email Setup Required", 
                    "Email is not configured!\n\n"
                    "Steps to setup:\n"
                    "1. Go to Settings tab\n"
                    "2. Enter SMTP server (e.g., smtp.gmail.com)\n"
                    "3. Enter SMTP port (587 for TLS, 465 for SSL)\n"
                    "4. Enter your email address\n"
                    "5. Enter App Password (for Gmail)\n"
                    "6. Enter receiver email(s), comma-separated\n"
                    "7. Click 'Save Email Config'\n"
                    "8. Click 'Test Email' to verify\n\n"
                    "For Gmail App Password:\n"
                    "https://myaccount.google.com/apppasswords")
                return
            
            if not email_config.sender_password:
                messagebox.showerror("Error", 
                    "Password is empty!\n\n"
                    "Please go to Settings tab and re-save your email config.\n"
                    "Make sure to enter your App Password.")
                return
            
            # Ask user what type of report to send
            choice = messagebox.askyesnocancel("Email Report Type", 
                f"Choose report type:\n\n"
                f"YES = Watchlist Scan Report ({len(self.watchlist)} stocks)\n"
                f"  → Analyzes your watchlist stocks and sends results\n\n"
                f"NO = Full Market Report\n"
                f"  → Analyzes Nifty 50, Sensex 30, US markets\n\n"
                f"CANCEL = Cancel")
            
            if choice is None:  # Cancel
                return
            elif choice:  # Yes - Watchlist
                if not self.results:
                    messagebox.showwarning("Warning", 
                        "No scan results! Please scan your watchlist first (F5).\n\n"
                        "Then try sending email again.")
                    return
                self._send_watchlist_email(email_config)
            else:  # No - Full market
                self._send_full_market_email(email_config)
            
        except ImportError:
            messagebox.showerror("Error", "Daily report module not found!")
        except Exception as e:
            self.status_lbl.configure(text="Ready")
            messagebox.showerror("Error", f"Email failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _send_watchlist_email(self, email_config):
        """Send watchlist scan results via email."""
        if not messagebox.askyesno("Send Watchlist Report", 
            f"Send watchlist scan report?\n\n"
            f"From: {email_config.sender_email}\n"
            f"To: {', '.join(email_config.receiver_emails)}\n"
            f"Stocks: {len(self.results)} scanned"):
            return
        
        self.status_lbl.configure(text="Generating watchlist report...")
        self.root.update()
        
        def do_send():
            try:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                from email.mime.base import MIMEBase
                from email import encoders
                
                self.root.after(0, lambda: self.status_lbl.configure(text="Building email..."))
                
                # Build HTML report
                html = self._build_watchlist_email_html()
                
                # Generate PDF attachment if possible
                pdf_path = None
                if REPORTLAB_OK:
                    try:
                        pdf_path = self._generate_watchlist_pdf()
                    except Exception as e:
                        print(f"PDF generation failed: {e}")
                
                # Create email
                msg = MIMEMultipart()
                msg['From'] = email_config.sender_email
                msg['To'] = ', '.join(email_config.receiver_emails)
                msg['Subject'] = f"[DR. NILESH SHAH'S] Watchlist Report - {datetime.now().strftime('%Y-%m-%d')}"
                msg.attach(MIMEText(html, 'html'))
                
                # Attach PDF if generated
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, 'rb') as f:
                        attachment = MIMEBase('application', 'octet-stream')
                        attachment.set_payload(f.read())
                        encoders.encode_base64(attachment)
                        attachment.add_header('Content-Disposition', 
                            f'attachment; filename={os.path.basename(pdf_path)}')
                        msg.attach(attachment)
                
                # Send
                self.root.after(0, lambda: self.status_lbl.configure(text="Sending email..."))
                
                if email_config.smtp_port == 465:
                    server = smtplib.SMTP_SSL(email_config.smtp_server, email_config.smtp_port, timeout=30)
                else:
                    server = smtplib.SMTP(email_config.smtp_server, email_config.smtp_port, timeout=30)
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                
                server.login(email_config.sender_email, email_config.sender_password)
                server.send_message(msg)
                server.quit()
                
                self.root.after(0, lambda: self.status_lbl.configure(text="Email sent!"))
                self.root.after(0, lambda: messagebox.showinfo("Email Sent!", 
                    f"Watchlist report sent successfully!\n\n"
                    f"Stocks: {len(self.results)}\n"
                    f"Sent to: {', '.join(email_config.receiver_emails)}"))
                
            except Exception as e:
                self.root.after(0, lambda: self.status_lbl.configure(text="Email failed"))
                self.root.after(0, lambda err=e: messagebox.showerror("Email Failed", f"Error: {err}"))
                import traceback
                traceback.print_exc()
        
        threading.Thread(target=do_send, daemon=True).start()
    
    def _build_watchlist_email_html(self):
        """Build HTML email from watchlist scan results."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Count recommendations
        sb = sum(1 for r in self.results if r['rec'] == 'STRONG BUY')
        buy = sum(1 for r in self.results if r['rec'] == 'BUY')
        hold = sum(1 for r in self.results if r['rec'] == 'HOLD')
        sell = sum(1 for r in self.results if r['rec'] == 'SELL')
        ss = sum(1 for r in self.results if r['rec'] == 'STRONG SELL')
        avg_score = sum(r['score'] for r in self.results) / len(self.results) if self.results else 0
        
        # Sort by score descending
        sorted_results = sorted(self.results, key=lambda x: x['score'], reverse=True)
        
        html = f"""
        <html>
        <head><style>
            body {{ font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }}
            .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #1f6feb, #0d1b2a); color: white; padding: 25px; text-align: center; }}
            .stats {{ display: flex; justify-content: space-around; padding: 20px; background: #f8fafc; flex-wrap: wrap; }}
            .stat {{ text-align: center; padding: 10px; }}
            .stat .num {{ font-size: 28px; font-weight: bold; }}
            .stat .label {{ font-size: 12px; color: #666; }}
            .section {{ padding: 20px; }}
            h2 {{ color: #1f6feb; border-bottom: 2px solid #1f6feb; padding-bottom: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 12px; }}
            th {{ background: #1f6feb; color: white; padding: 10px 8px; text-align: center; }}
            td {{ padding: 8px; border-bottom: 1px solid #eee; text-align: center; }}
            tr:nth-child(even) {{ background: #f9fafb; }}
            .strong-buy {{ background: #059669; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; }}
            .buy {{ background: #10b981; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; }}
            .hold {{ background: #d97706; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; }}
            .sell {{ background: #ef4444; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; }}
            .strong-sell {{ background: #dc2626; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; }}
            .footer {{ background: #1f2937; color: #9ca3af; padding: 15px; text-align: center; font-size: 11px; }}
            .top-pick {{ background: #ecfdf5; }}
            .avoid {{ background: #fef2f2; }}
        </style></head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>DR. NILESH SHAH'S MARKET ANALYSIS</h1>
                    <h2>Watchlist Scan Report</h2>
                    <p>{now}</p>
                </div>
                <div class="stats">
                    <div class="stat"><div class="num">{len(self.results)}</div><div class="label">Total Scanned</div></div>
                    <div class="stat"><div class="num" style="color:#059669">{sb}</div><div class="label">Strong Buy</div></div>
                    <div class="stat"><div class="num" style="color:#10b981">{buy}</div><div class="label">Buy</div></div>
                    <div class="stat"><div class="num" style="color:#d97706">{hold}</div><div class="label">Hold</div></div>
                    <div class="stat"><div class="num" style="color:#ef4444">{sell + ss}</div><div class="label">Sell</div></div>
                    <div class="stat"><div class="num">{avg_score:.1f}</div><div class="label">Avg Score</div></div>
                </div>
        """
        
        # Signal changes since the previous scan day (from the score history)
        changed = [r for r in sorted_results if r.get('prev_rec') and r['prev_rec'] != r['rec']]
        if changed:
            html += '<div class="section"><h2>Signal Changes Since Last Scan</h2><table>'
            html += '<tr><th>Symbol</th><th>Before</th><th>Now</th><th>Score</th><th>Score Chg</th><th>Since</th></tr>'
            for r in changed:
                html += (f'<tr><td><b>{r["symbol"]}</b></td><td>{r["prev_rec"]}</td>'
                         f'<td><span class="{r["rec"].lower().replace(" ", "-")}">{r["rec"]}</span></td>'
                         f'<td>{r["score"]:.0f}</td><td>{r["score"] - r["prev_score"]:+.1f}</td><td>{r.get("prev_date", "")}</td></tr>')
            html += '</table></div>'

        # Top picks section
        top_picks = [r for r in sorted_results if r['rec'] in ['STRONG BUY', 'BUY']][:5]
        if top_picks:
            html += '<div class="section"><h2>Top Picks</h2><table>'
            html += '<tr><th>Symbol</th><th>Price</th><th>Change%</th><th>RSI</th><th>Score</th><th>Signal</th><th>Stop Loss</th><th>Target 1</th><th>R:R</th></tr>'
            for r in top_picks:
                t = r.get('targets', {})
                html += f'<tr class="top-pick"><td><b>{r["symbol"]}{"*" if r.get("hourly") else ""}</b></td><td>{r["price"]:.2f}</td><td>{r["change"]:+.2f}%</td><td>{r["rsi"]:.0f}</td><td><b>{r["score"]:.0f}</b></td><td><span class="{r["rec"].lower().replace(" ", "-")}">{r["rec"]}</span></td><td>{t.get("sl", "N/A")}</td><td>{t.get("t1", "N/A")}</td><td>1:{t.get("rr", 0)}</td></tr>'
            html += '</table></div>'
        
        # All results table
        html += '<div class="section"><h2>All Watchlist Results</h2><table>'
        html += '<tr><th>#</th><th>Symbol</th><th>Price</th><th>Change%</th><th>vs Nifty 3M</th><th>RSI</th><th>SuperTrend</th><th>Score</th><th>Signal</th><th>Stop Loss</th><th>Target 1</th><th>Traded/day (Cr)</th></tr>'

        for i, r in enumerate(sorted_results, 1):
            t = r.get('targets', {})
            rec_class = r['rec'].lower().replace(' ', '-')
            row_class = 'top-pick' if r['rec'] in ['STRONG BUY', 'BUY'] else 'avoid' if r['rec'] in ['SELL', 'STRONG SELL'] else ''
            rs3 = (r.get('rs') or {}).get('3M')
            rs_cell = f"{rs3:+.1f}%" if rs3 is not None else "N/A"
            html += f'<tr class="{row_class}"><td>{i}</td><td><b>{r["symbol"]}{"*" if r.get("hourly") else ""}</b></td><td>{r["price"]:.2f}</td><td>{r["change"]:+.2f}%</td><td>{rs_cell}</td><td>{r["rsi"]:.0f}</td><td>{r.get("st_sig", "")}</td><td>{r["score"]:.0f}</td><td><span class="{rec_class}">{r["rec"]}</span></td><td>{t.get("sl", "N/A")}</td><td>{t.get("t1", "N/A")}</td><td>{self._liquidity_text(r)}</td></tr>'
        
        html += '</table>'
        html += (f'<p style="font-size:11px;color:#666">LOW = average traded value below Rs {self.min_liquidity_cr:g} crore/day: '
                 'stop-loss and targets are less reliable for these stocks.</p>')
        if any(r.get('hourly') for r in self.results):
            html += f'<p style="font-size:11px;color:#666">{market_data.HOURLY_NOTE}</p>'
        html += '</div>'
        
        # Stocks to avoid
        avoid_list = [r for r in sorted_results if r['rec'] in ['SELL', 'STRONG SELL']][:5]
        if avoid_list:
            html += '<div class="section"><h2>Stocks to Avoid</h2><table>'
            html += '<tr><th>Symbol</th><th>Price</th><th>Score</th><th>Signal</th></tr>'
            for r in avoid_list:
                html += f'<tr class="avoid"><td><b>{r["symbol"]}</b></td><td>{r["price"]:.2f}</td><td>{r["score"]:.0f}</td><td><span class="{r["rec"].lower().replace(" ", "-")}">{r["rec"]}</span></td></tr>'
            html += '</table></div>'
        
        html += f"""
                <div class="footer">
                    <p>DR. NILESH SHAH'S MARKET ANALYSIS | For educational purposes only</p>
                    <p>Generated: {now} | Stocks: {len(self.results)}</p>
                </div>
            </div>
        </body></html>
        """
        return html
    
    def _generate_watchlist_pdf(self):
        """Generate PDF for watchlist report."""
        if not REPORTLAB_OK:
            return None
        
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
        pdf_file = os.path.join(str(DATA_DIR), 'reports', 
                                f'watchlist_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
        os.makedirs(os.path.dirname(pdf_file), exist_ok=True)
        
        logo = pdf_logo(LOGO_PATH) if LOGO_PATH.exists() else None

        def add_header(canvas_obj, doc):
            canvas_obj.saveState()
            if logo:
                try:
                    canvas_obj.drawImage(logo, 25, A4[1] - 75,
                                       width=45, height=45, preserveAspectRatio=True, mask='auto')
                except: pass
            canvas_obj.setFont('Helvetica-Bold', 14)
            canvas_obj.setFillColor(colors.HexColor('#1f6feb'))
            canvas_obj.drawString(80, A4[1] - 50, "DR. NILESH SHAH'S MARKET ANALYSIS")
            canvas_obj.setFont('Helvetica', 9)
            canvas_obj.setFillColor(colors.gray)
            canvas_obj.drawString(80, A4[1] - 65, f"Watchlist Report | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            canvas_obj.setStrokeColor(colors.HexColor('#1f6feb'))
            canvas_obj.setLineWidth(2)
            canvas_obj.line(25, A4[1] - 85, A4[0] - 25, A4[1] - 85)
            canvas_obj.setFont('Helvetica', 7)
            canvas_obj.drawString(25, 25, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            canvas_obj.drawRightString(A4[0] - 25, 25, f"Page {doc.page}")
            canvas_obj.restoreState()
        
        doc = SimpleDocTemplate(pdf_file, pagesize=A4, topMargin=100, bottomMargin=60, leftMargin=25, rightMargin=25)
        elements = []
        styles = getSampleStyleSheet()
        
        sorted_results = sorted(self.results, key=lambda x: x['score'], reverse=True)
        
        # Summary
        sb = sum(1 for r in self.results if r['rec'] == 'STRONG BUY')
        buy = sum(1 for r in self.results if r['rec'] == 'BUY')
        hold = sum(1 for r in self.results if r['rec'] == 'HOLD')
        sell = sum(1 for r in self.results if r['rec'] == 'SELL')
        ss = sum(1 for r in self.results if r['rec'] == 'STRONG SELL')
        avg = sum(r['score'] for r in self.results) / len(self.results) if self.results else 0
        
        elements.append(Paragraph("WATCHLIST SCAN REPORT", ParagraphStyle('T', parent=styles['Title'], fontSize=16, textColor=colors.HexColor('#1f6feb'))))
        elements.append(Spacer(1, 10))
        
        summary_data = [['Total', 'Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell', 'Avg Score'],
                        [str(len(self.results)), str(sb), str(buy), str(hold), str(sell), str(ss), f"{avg:.1f}"]]
        t = Table(summary_data, colWidths=[60, 70, 50, 50, 50, 70, 60])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f6feb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, 1), 12),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 15))
        
        # Results table
        elements.append(Paragraph("Detailed Results", ParagraphStyle('H', parent=styles['Heading2'], fontSize=12)))
        elements.append(Spacer(1, 10))
        
        data = [['#', 'Symbol', 'Price', 'Chg%', 'RSI', 'ST', 'Score', 'Signal', 'SL', 'T1', 'R:R']]
        for i, r in enumerate(sorted_results, 1):
            t_data = r.get('targets', {})
            data.append([
                str(i), r['symbol'] + ('*' if r.get('hourly') else ''), f"{r['price']:.2f}", f"{r['change']:+.1f}%",
                f"{r['rsi']:.0f}", r.get('st_sig', ''), f"{r['score']:.0f}", r['rec'],
                f"{t_data.get('sl', 'N/A')}", f"{t_data.get('t1', 'N/A')}", f"1:{t_data.get('rr', 0)}"
            ])
        
        t = Table(data, colWidths=[25, 60, 50, 40, 35, 35, 40, 70, 50, 50, 35])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f6feb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        elements.append(t)
        if any(r.get('hourly') for r in self.results):
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(market_data.HOURLY_NOTE, ParagraphStyle('N', parent=styles['Normal'], fontSize=8, textColor=colors.gray)))

        doc.build(elements, onFirstPage=add_header, onLaterPages=add_header)
        return pdf_file
    
    def _send_full_market_email(self, email_config):
        """Send full market report via email."""
        if not messagebox.askyesno("Send Full Market Report", 
            f"Send full market report?\n\n"
            f"From: {email_config.sender_email}\n"
            f"To: {', '.join(email_config.receiver_emails)}\n\n"
            f"This will analyze Nifty 50, Sensex 30, and US markets.\n"
            f"May take a few minutes..."):
            return
        
        self.status_lbl.configure(text="Generating report and sending email...")
        self.root.update()
        
        def do_send():
            try:
                from daily_report import DailyReportGenerator
                generator = DailyReportGenerator()
                
                self.root.after(0, lambda: self.status_lbl.configure(text="Analyzing markets..."))
                report = generator.generate_report(include_us=True, include_india=True)
                
                self.root.after(0, lambda: self.status_lbl.configure(text="Generating PDF..."))
                pdf_path = generator.generate_pdf_report(report)
                
                self.root.after(0, lambda: self.status_lbl.configure(text="Sending email..."))
                success = generator.send_email_report(report, pdf_path)
                
                if success:
                    summary = report.get('summary', {})
                    self.root.after(0, lambda: self.status_lbl.configure(text="Email sent!"))
                    self.root.after(0, lambda: messagebox.showinfo("Email Sent!", 
                        f"Report sent successfully!\n\n"
                        f"Stocks Analyzed: {summary.get('total_stocks', 0)}\n"
                        f"Buy: {summary.get('strong_buy', 0) + summary.get('buy', 0)}\n"
                        f"Hold: {summary.get('hold', 0)}\n"
                        f"Sell: {summary.get('sell', 0) + summary.get('strong_sell', 0)}\n"
                        f"Sent to: {', '.join(email_config.receiver_emails)}"))
                else:
                    error_msg = generator.email_config.last_error if hasattr(generator, 'email_config') else "Unknown error"
                    self.root.after(0, lambda: self.status_lbl.configure(text="Email failed"))
                    self.root.after(0, lambda: messagebox.showerror("Email Failed", 
                        f"Failed to send email!\n\n{error_msg}"))
                    
            except Exception as e:
                self.root.after(0, lambda: self.status_lbl.configure(text="Error"))
                self.root.after(0, lambda err=e: messagebox.showerror("Error", f"Email failed: {err}"))
                import traceback
                traceback.print_exc()
        
        threading.Thread(target=do_send, daemon=True).start()


def _self_test():
    """Check that every part of the (packaged) app works. Run: "DR Nilesh Shah Market Analysis.exe" --self-test
    Results are written to self_test_result.txt next to the .exe."""
    import tempfile
    lines, failed = [f"Self-test {datetime.now():%Y-%m-%d %H:%M:%S} | frozen={FROZEN} | data folder: {DATA_DIR}"], []

    def check(name, fn):
        try:
            lines.append(f"PASS  {name}: {fn()}")
        except Exception as e:
            failed.append(name)
            lines.append(f"FAIL  {name}: {type(e).__name__}: {e}")

    def modules():
        flags = dict(market_data=MARKET_DATA_OK, backtest=BACKTEST_OK, scheduler=SCHEDULER_OK, report=REPORT_OK,
                     score_history=HISTORY_OK,
                     patterns=PATTERN_OK, corp_engine=CORP_ENGINE_OK, charts=MATPLOTLIB_OK, pdf_export=REPORTLAB_OK,
                     pdf_import=PDF_OK, images=PIL_OK)
        missing = [k for k, v in flags.items() if not v]
        if missing:
            raise RuntimeError(f"not loaded: {missing}" + (f" (pdf_import: {PDF_IMPORT_ERROR})" if PDF_IMPORT_ERROR else ""))
        return "all loaded"
    check("modules", modules)
    check("logo", lambda: f"{LOGO_PATH.exists()} ({LOGO_PATH.name})" if LOGO_PATH.exists() else 1 / 0)

    data = {}
    def prices():
        data.update(market_data.load_history(['RELIANCE', 'CREATIVE'], years=2))
        return {s: len(df) for s, df in data.items()}
    check("price download (NSE + BSE fallback)", prices)
    check("analysis + score", lambda: (lambda d: f"{Scorer.score(d)['total']} / patterns {d['patterns']['summary']['total_patterns']}")(
        Analyzer().analyze(data['RELIANCE'])))

    def targets():
        d = Analyzer().analyze(data['RELIANCE'])
        t = TargetCalc.calc(d, Scorer.score(d)['rec'])
        if not t.get('basis') or min(t['sl'], t['t1'], t['t2'], t['t3']) <= 0:
            raise RuntimeError(str(t))
        return f"stop {t['sl']} ({t['basis']['sl']}), target 1 {t['t1']} ({t['basis']['t1']}), risk:reward 1:{t['rr']}"
    check("stop-loss and targets (support/resistance)", targets)

    def vs_nifty():
        nifty = market_data.load_history([NIFTY_SYMBOL], years=2, exchange='INDEX').get(NIFTY_SYMBOL)
        if nifty is None or len(nifty) < 130:
            raise RuntimeError("Nifty 50 history not available")
        rs = relative_strength(data['RELIANCE'], nifty)
        if rs['3M'] is None:
            raise RuntimeError(f"no 3-month figure: {rs}")
        return f"RELIANCE vs Nifty 50: {rs}"
    check("relative strength (Nifty 50)", vs_nifty)

    def hourly_candles():   # what new listings are scanned on: built from 15-minute candles
        ticker = 'RELIANCE.NS'
        df = market_data._hourly(market_data._download([ticker], tz=market_data.HOURLY_TZ, period='5d', interval='15m')[ticker])
        first_hour = df[df.index.strftime('%H:%M') == '09:15']
        if not market_data.is_hourly(df) or len(first_hour) < 2 or first_hour['Volume'].sum() <= 0:
            raise RuntimeError(f"{len(df)} candles, {len(first_hour)} of them 09:15-10:15")
        return f"{len(df)} candles over {Analyzer().analyze(df)['days']} days"
    check("1-hour candles (new listings)", hourly_candles)

    def report_parts():   # the daily report must score a stock exactly as the scan does
        import daily_report
        r = daily_report.StockAnalyzer().analyze('RELIANCE', 'NSE', data['RELIANCE'])
        scan = Scorer.score(Analyzer().analyze(data['RELIANCE']))
        if r is None or abs(r['score'] - scan['total']) > 0.05 or r['recommendation'] != scan['rec']:
            raise RuntimeError(f"report {r and r['score']} vs scan {scan['total']}")
        if isinstance(pdf_logo(LOGO_PATH), str):
            raise RuntimeError("small logo for PDFs could not be made")
        return (f"score {r['score']} {r['recommendation']} as in the scan, {len(daily_report.nifty50_stocks())} Nifty 50 stocks, "
                f"{len(daily_report.NewsFetcher().fetch_news(max_articles=5))} news headlines")
    check("daily report (same score as the scan)", report_parts)
    def full_backtest():   # the whole thing incl. statistics (SciPy-free since 1 Oct fix)
        r = backtest.run_backtest(data, Scorer, dict(Scorer.WEIGHTS), 10)
        if 'error' in r:
            raise RuntimeError(r['error'])
        return f"{r['n_samples']} stock-days, power {r['current']['ic']:+.3f}"
    check("backtest (full)", full_backtest)
    check("sector lookup", lambda: market_data.get_sectors(['RELIANCE']))

    def keyring_backend():
        import daily_report, keyring
        if not daily_report.KEYRING_OK:
            raise RuntimeError(type(keyring.get_keyring()).__name__)
        return type(keyring.get_keyring()).__name__
    check("Windows Credential Manager", keyring_backend)

    def chart():
        root = tk.Tk(); root.withdraw()
        fig = Figure(figsize=(4, 3)); fig.add_subplot(111).plot([1, 2, 3])
        FigureCanvasTkAgg(fig, master=root).draw(); root.destroy()
        return f"TkAgg on Tk {tk.TkVersion}"
    def company_search():
        found = symbols.search('relia', 5)
        if len(symbols.load()) < 3000 or not found or found[0][symbols.ADD] != 'RELIANCE':
            raise RuntimeError(f"{len(symbols.load())} companies, 'relia' -> {found[:1]}")
        e = found[0]
        return (f"{len(symbols.load())} companies; 'relia' -> {e[symbols.NAME]} (NSE {e[symbols.NSE]}, BSE {e[symbols.BSE]} {e[symbols.CODE]}); "
                f"'tata cons' -> {[x[symbols.ADD] for x in symbols.search('tata cons', 2)]}")
    check("company search (NSE + BSE list)", company_search)

    check("chart", chart)

    def chart_3d():      # the 3D market map and the 3D sector chart
        root = tk.Tk(); root.withdraw()
        fig = Figure(figsize=(4, 3))
        ax = fig.add_subplot(111, projection='3d')
        ax.scatter([10, 50, 70], [-5, 0, 8], [30, 50, 80], depthshade=True)
        ax.bar3d(0, 0, 0, 0.6, 0.6, 3, shade=True)
        ax.view_init(elev=24, azim=-60)
        FigureCanvasTkAgg(fig, master=root).draw(); root.destroy()
        return "3D scatter and bars drawn"
    check("3D charts", chart_3d)

    def look():          # both colour schemes, fonts, 3D buttons and signal markers
        root = tk.Tk(); root.withdraw()
        ui.init_fonts(root)
        for mode in ('light', 'dark'):
            T = ui.palette(mode)
            ui.style_ttk(root, T)
            ui.marker_images(T)
            ui.RoundButton(root, "Test", kind='primary', theme=T).invoke()
            ui.SummaryCard(root, T).update_values({'BUY': 1}, 1, 60.0, animate=False)
        root.destroy()
        return f"light + dark; fonts {ui.FONT} / {ui.DISPLAY}"
    check("look (light and dark)", look)

    def pdf():
        path = os.path.join(tempfile.gettempdir(), 'dr_shah_selftest.pdf')
        SimpleDocTemplate(path, pagesize=A4).build([Paragraph("Self-test", getSampleStyleSheet()['Normal'])])
        with pdfplumber.open(path) as p:
            text = p.pages[0].extract_text()
        os.remove(path)
        return f"written and read back ('{text.strip()}')"
    check("PDF export + import", pdf)
    check("NSE corporate actions", lambda: f"{len(CorporateActionsEngine().nse.fetch_all_actions())} actions")
    check("NSE holiday calendar", lambda: f"{len(scheduled_report._nse_holidays(datetime.now().year))} holidays")
    check("market light", lambda: market_status(datetime.now(), scheduled_report.cached_holidays(datetime.now().year))[1])

    lines.append("RESULT: " + ("ALL PASSED" if not failed else f"{len(failed)} FAILED: {', '.join(failed)}"))
    (DATA_DIR / "self_test_result.txt").write_text("\n".join(lines), encoding='utf-8')
    return 0 if not failed else 1


_INSTANCE_LOCK = None


def main():
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    if '--scheduled-report' in sys.argv:
        # Started by Windows Task Scheduler (packaged .exe): email the report without opening the window
        import scheduled_report
        sys.exit(scheduled_report.main())
    global _INSTANCE_LOCK
    _INSTANCE_LOCK = single_instance_lock()
    if _INSTANCE_LOCK is None:
        logger.info("Second copy started - switching to the one already running")
        if not focus_running_app():
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(APP_TITLE, "The app is already running.\n\nOnly one copy can run at a time, "
                                           "so your watchlist and settings aren't overwritten.")
            root.destroy()
        return
    try:
        root = tk.Tk()
        app = App(root)
        root.mainloop()
    except Exception as e:
        logger.exception("Fatal error")
        if FROZEN:   # no console to show the error in
            messagebox.showerror("DR. NILESH SHAH'S MARKET ANALYSIS",
                                 f"The app could not start:\n\n{e}\n\nDetails are in dr_shah_analysis.log")
        else:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            input("Press Enter...")


if __name__ == "__main__":
    main()
