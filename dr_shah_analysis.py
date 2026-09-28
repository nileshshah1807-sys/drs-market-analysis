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

# Pattern Recognition
PATTERN_OK = False
try:
    from pattern_recognition import PatternDetector, PatternFormatter
    PATTERN_OK = True
except ImportError:
    pass

# AI/ML Engine
AI_OK = False
try:
    from ai_engine import AIEngine
    AI_OK = True
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
    import matplotlib.pyplot as plt
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

# Logging
from app_paths import FROZEN, DATA_DIR, RESOURCE_DIR
log_file = str(DATA_DIR / 'dr_shah_analysis.log')
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s', filemode='a')
logger = logging.getLogger(__name__)
# yfinance logs every .NS miss (BSE-only stocks fall back to .BO) - keep the app log readable
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

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

THEME = {
    'bg': '#0b0f1a', 'bg2': '#0f1629', 'bg3': '#151d33',
    'card': '#131b2e', 'card2': '#1a2540', 'input': '#0d1525',
    'fg': '#e8ecf4', 'fg2': '#94a3b8', 'fg3': '#64748b',
    'accent': '#3b82f6', 'accent2': '#60a5fa', 'accent3': '#818cf8',
    'success': '#10b981', 'success2': '#34d399',
    'warning': '#f59e0b', 'warning2': '#fbbf24',
    'danger': '#ef4444', 'danger2': '#f87171',
    'buy': '#059669', 'sell': '#dc2626', 'hold': '#d97706',
    'border': '#1e293b', 'glow': '#3b82f6', 'gold': '#fbbf24',
    'purple': '#a78bfa', 'cyan': '#22d3ee', 'pink': '#f472b6',
    'orange': '#fb923c', 'lime': '#a3e635',
}


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def safe_float(v, d=0.0):
    try:
        if v is None: return d
        val = float(v)
        return d if (pd.isna(val) or np.isnan(val) or np.isinf(val)) else val
    except: return d


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
        self.pattern_detector = PatternDetector() if PATTERN_OK else None
        self.ai_engine = AIEngine() if AI_OK else None
    
    def fetch(self, symbol, period="2y"):
        key = f"{symbol}_{period}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        if MARKET_DATA_OK:
            df = market_data.load_history([symbol], years=HISTORY_YEARS).get(symbol.upper())
            df = market_data.slice_period(df, period) if df is not None else None
            if df is not None and len(df) >= 20:
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
        """Fetch many symbols at once (one batch download + disk cache). Returns {symbol: df}."""
        if not MARKET_DATA_OK:
            out = {}
            for s in symbols:
                df = self.fetch(s, period)
                if df is not None and not df.empty:
                    out[s] = df
            return out
        data = market_data.load_history(symbols, years=HISTORY_YEARS, progress=progress)
        out = {}
        for s in symbols:
            df = data.get(s.upper())
            if df is not None:
                df = market_data.slice_period(df, period)
                if len(df) >= 20:
                    out[s] = df
                    self.cache.set(f"{s}_{period}", df)
        return out

    def analyze(self, df, with_ai=False):
        if df is None or df.empty:
            raise ValueError("No data")
        
        price = safe_float(df['Close'].iloc[-1])
        prev = safe_float(df['Close'].iloc[-2]) if len(df) > 1 else price

        # Liquidity: average daily traded value over the last 20 sessions, in Rs crore
        try: liquidity_cr = safe_float((df['Close'] * df['Volume']).tail(20).mean() / 1e7)
        except: liquidity_cr = 0.0

        # RSI
        try: rsi = safe_float(ta.momentum.RSIIndicator(df['Close'], 14).rsi().iloc[-1], 50)
        except: rsi = 50.0
        
        # MACD (None when there isn't enough history - ~35 days - so it scores neutral instead of bearish)
        try:
            m = ta.trend.MACD(df['Close'])
            macd = {'macd': safe_float(m.macd().iloc[-1], None), 'signal': safe_float(m.macd_signal().iloc[-1], None),
                    'hist': safe_float(m.macd_diff().iloc[-1], None)}
        except: macd = {'macd': None, 'signal': None, 'hist': None}

        # Moving Averages - None when the stock is too new for that average (it's then skipped
        # by the scorer; treating it as equal to the price used to count as a bearish signal)
        try:
            ma = {
                'sma20': safe_float(ta.trend.SMAIndicator(df['Close'], 20).sma_indicator().iloc[-1], None),
                'sma50': safe_float(ta.trend.SMAIndicator(df['Close'], 50).sma_indicator().iloc[-1], None) if len(df) >= 50 else None,
                'sma200': safe_float(ta.trend.SMAIndicator(df['Close'], 200).sma_indicator().iloc[-1], None) if len(df) >= 200 else None,
                'ema12': safe_float(ta.trend.EMAIndicator(df['Close'], 12).ema_indicator().iloc[-1], None),
                'ema26': safe_float(ta.trend.EMAIndicator(df['Close'], 26).ema_indicator().iloc[-1], None)
            }
        except: ma = {'sma20': None, 'sma50': None, 'sma200': None, 'ema12': None, 'ema26': None}
        
        # Bollinger
        try:
            bb = ta.volatility.BollingerBands(df['Close'])
            boll = {'upper': safe_float(bb.bollinger_hband().iloc[-1]), 'lower': safe_float(bb.bollinger_lband().iloc[-1])}
        except: boll = {'upper': price * 1.02, 'lower': price * 0.98}
        
        # Stochastic
        try:
            s = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
            stoch = {'k': safe_float(s.stoch().iloc[-1], 50), 'd': safe_float(s.stoch_signal().iloc[-1], 50)}
        except: stoch = {'k': 50, 'd': 50}
        
        # ADX
        try: adx = safe_float(ta.trend.ADXIndicator(df['High'], df['Low'], df['Close']).adx().iloc[-1], 25)
        except: adx = 25.0
        
        # OBV
        try:
            obv_s = ta.volume.OnBalanceVolumeIndicator(df['Close'], df['Volume']).on_balance_volume()
            obv_curr = safe_float(obv_s.iloc[-1])
            obv_prev = safe_float(obv_s.iloc[-5]) if len(obv_s) >= 5 else obv_curr
            obv_trend = ((obv_curr - obv_prev) / abs(obv_prev) * 100) if obv_prev != 0 else 0
        except: obv_trend = 0.0
        
        # Williams %R
        try: wr = safe_float(ta.momentum.WilliamsRIndicator(df['High'], df['Low'], df['Close']).williams_r().iloc[-1], -50)
        except: wr = -50.0
        
        # CCI
        try: cci = safe_float(ta.trend.CCIIndicator(df['High'], df['Low'], df['Close']).cci().iloc[-1], 0)
        except: cci = 0.0
        
        # ATR
        try: atr = safe_float(ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], 14).average_true_range().iloc[-1])
        except: atr = price * 0.02
        if atr == 0: atr = price * 0.02
        
        # SuperTrend (PROPER implementation)
        try:
            period = 10
            multiplier = 3.0
            high = df['High'].values
            low = df['Low'].values
            close = df['Close'].values
            
            tr1 = high - low
            tr2 = abs(high - np.roll(close, 1))
            tr3 = abs(low - np.roll(close, 1))
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            tr[0] = tr1[0]
            
            atr_st = pd.Series(tr).ewm(span=period, adjust=False).mean().values
            hl2 = (high + low) / 2
            basic_ub = hl2 + (multiplier * atr_st)
            basic_lb = hl2 - (multiplier * atr_st)
            
            final_ub = np.zeros_like(close)
            final_lb = np.zeros_like(close)
            supertrend = np.zeros_like(close)
            direction = np.zeros_like(close)
            
            final_ub[0] = basic_ub[0]
            final_lb[0] = basic_lb[0]
            supertrend[0] = close[0]
            direction[0] = 1
            
            for i in range(1, len(close)):
                final_ub[i] = basic_ub[i] if (basic_ub[i] < final_ub[i-1] or close[i-1] > final_ub[i-1]) else final_ub[i-1]
                final_lb[i] = basic_lb[i] if (basic_lb[i] > final_lb[i-1] or close[i-1] < final_lb[i-1]) else final_lb[i-1]
                
                if direction[i-1] == 1:
                    if close[i] < final_lb[i]:
                        direction[i] = -1
                        supertrend[i] = final_ub[i]
                    else:
                        direction[i] = 1
                        supertrend[i] = final_lb[i]
                else:
                    if close[i] > final_ub[i]:
                        direction[i] = 1
                        supertrend[i] = final_lb[i]
                    else:
                        direction[i] = -1
                        supertrend[i] = final_ub[i]
            
            st_sig = 'BUY' if direction[-1] == 1 else 'SELL'
            st_dir = 'BULLISH' if direction[-1] == 1 else 'BEARISH'
            st_val = round(safe_float(supertrend[-1]), 2)
        except Exception as e:
            logger.warning(f"SuperTrend error: {e}")
            st_val, st_sig, st_dir = price, 'HOLD', 'NEUTRAL'
        
        # VWAP
        try:
            tp = (df['High'] + df['Low'] + df['Close']) / 3
            vwap = safe_float((tp * df['Volume']).rolling(20).sum().iloc[-1] / df['Volume'].rolling(20).sum().iloc[-1])
            if vwap == 0: vwap = price
            vwap_sig = 'BULLISH' if price > vwap * 1.02 else 'BEARISH' if price < vwap * 0.98 else 'NEUTRAL'
        except:
            vwap, vwap_sig = price, 'NEUTRAL'
        
        # Pattern Detection
        patterns = {}
        if self.pattern_detector:
            try: patterns = self.pattern_detector.detect_all_patterns(df)
            except: patterns = {'chart': [], 'candlestick': [], 'harmonic': [], 'summary': {}}
        
        # AI Analysis
        # Skipped in scans by default: it retrains ML models per stock (~0.5s each) and its
        # output isn't used by the score or shown anywhere.
        ai_results = {}
        if with_ai and self.ai_engine:
            try: ai_results = self.ai_engine.full_analysis(df)
            except: ai_results = {}
        
        return {
            'price': price, 'prev': prev, 'liquidity_cr': liquidity_cr, 'rsi': rsi, 'macd': macd, 'ma': ma,
            'boll': boll, 'stoch': stoch, 'adx': adx, 'obv_trend': obv_trend,
            'wr': wr, 'cci': cci, 'atr': atr,
            'supertrend': {'val': st_val, 'sig': st_sig, 'dir': st_dir},
            'vwap': {'val': vwap, 'sig': vwap_sig},
            'patterns': patterns, 'ai': ai_results
        }


# ============================================================
# SCORER
# ============================================================

class Scorer:
    WEIGHTS = {'rsi': 12, 'macd': 12, 'ma': 15, 'boll': 8, 'stoch': 8, 'adx': 8, 'vol': 8, 'mom': 8, 'st': 11, 'vwap': 10}
    DEFAULT_WEIGHTS = dict(WEIGHTS)
    
    @classmethod
    def score(cls, data):
        scores = {
            'rsi': cls._rsi(data['rsi']),
            'macd': cls._macd(data['macd']),
            'ma': cls._ma(data['price'], data['ma']),
            'boll': cls._boll(data['price'], data['boll']),
            'stoch': cls._stoch(data['stoch']),
            'adx': cls._adx(data['adx']),
            'vol': cls._vol(data['obv_trend']),
            'mom': cls._mom(data['wr'], data['cci']),
            'st': cls._st(data['supertrend']),
            'vwap': cls._vwap(data['vwap'])
        }
        total = sum(scores[k] * cls.WEIGHTS[k] / 100 for k in scores)
        rec = 'STRONG BUY' if total >= 75 else 'BUY' if total >= 60 else 'HOLD' if total >= 45 else 'SELL' if total >= 30 else 'STRONG SELL'
        return {'total': round(total, 1), 'breakdown': scores, 'rec': rec}
    
    @staticmethod
    def _rsi(v):
        v = safe_float(v, 50)
        return 90 if v < 20 else 75 if v < 30 else 60 if v < 40 else 50 if v < 50 else 45 if v < 60 else 35 if v < 70 else 20 if v < 80 else 10
    
    @staticmethod
    def _macd(m):
        if m.get('hist') is None or m.get('macd') is None or m.get('signal') is None:
            return 50   # not enough history for MACD - neutral
        s = 50 + (25 if safe_float(m['hist']) > 0 else -25) + (15 if safe_float(m['macd']) > safe_float(m['signal']) else -15)
        return max(0, min(100, s))

    @staticmethod
    def _ma(price, ma):
        s = 50
        for v in ma.values():
            if v is None:
                continue   # stock too new for this average - skip rather than count as bearish
            s += 10 if price > safe_float(v) else -10
        s50, s200 = ma.get('sma50'), ma.get('sma200')
        if s50 is not None and s200 is not None and s50 > 0 and s200 > 0:
            s += 10 if s50 > s200 else -10
        return max(0, min(100, s))
    
    @staticmethod
    def _boll(price, b):
        u, l = safe_float(b['upper']), safe_float(b['lower'])
        if u == l: return 50
        pos = (price - l) / (u - l)
        return 80 if pos < 0.1 else 65 if pos < 0.3 else 50 if pos < 0.5 else 40 if pos < 0.7 else 30 if pos < 0.9 else 15
    
    @staticmethod
    def _stoch(s):
        k, d = safe_float(s['k'], 50), safe_float(s['d'], 50)
        sc = 50 + (30 if k < 20 else 15 if k < 30 else -30 if k > 80 else -15 if k > 70 else 0)
        return max(0, min(100, sc + (10 if k > d else -10)))
    
    @staticmethod
    def _adx(v):
        v = safe_float(v, 25)
        return 80 if v > 50 else 70 if v > 40 else 60 if v > 30 else 50 if v > 20 else 30
    
    @staticmethod
    def _vol(v):
        v = safe_float(v)
        return 80 if v > 10 else 65 if v > 5 else 55 if v > 0 else 45 if v > -5 else 35 if v > -10 else 20
    
    @staticmethod
    def _mom(wr, cci):
        s = 50
        wr = safe_float(wr, -50)
        s += 20 if wr < -80 else (-20 if wr > -20 else 0)
        cci = safe_float(cci, 0)
        s += 15 if cci < -100 else (-15 if cci > 100 else 0)
        return max(0, min(100, s))
    
    @staticmethod
    def _st(st):
        sig, d = st.get('sig', 'HOLD'), st.get('dir', 'NEUTRAL')
        if sig == 'BUY' and d == 'BULLISH': return 85
        elif sig == 'BUY': return 65
        elif sig == 'SELL' and d == 'BEARISH': return 15
        elif sig == 'SELL': return 35
        return 50
    
    @staticmethod
    def _vwap(v):
        sig = v.get('sig', 'NEUTRAL')
        return 70 if sig == 'BULLISH' else 30 if sig == 'BEARISH' else 50


class TargetCalc:
    @staticmethod
    def calc(data, rec):
        price = data['price']
        atr = data['atr']
        if price <= 0: return {}
        
        r = {'price': round(price, 2), 'atr': round(atr, 2)}
        
        if rec in ['STRONG BUY', 'BUY']:
            sl = price - atr * 1.5
            r.update({'sl': round(sl, 2), 't1': round(price + atr * 1.5, 2), 't2': round(price + atr * 2.5, 2), 't3': round(price + atr * 4, 2),
                     'risk': round(price - sl, 2), 'reward': round(atr * 2.5, 2), 'pos': 'LONG'})
        elif rec in ['SELL', 'STRONG SELL']:
            sl = price + atr * 1.5
            r.update({'sl': round(sl, 2), 't1': round(price - atr * 1.5, 2), 't2': round(price - atr * 2.5, 2), 't3': round(price - atr * 4, 2),
                     'risk': round(sl - price, 2), 'reward': round(atr * 2.5, 2), 'pos': 'SHORT'})
        else:
            sl = price - atr * 1.5
            r.update({'sl': round(sl, 2), 't1': round(price + atr * 1.5, 2), 't2': round(price + atr * 2.5, 2), 't3': round(price - atr * 2.5, 2),
                     'risk': round(price - sl, 2), 'reward': round(atr * 1.5, 2), 'pos': 'HOLD'})
        
        r['rr'] = round(r['reward'] / r['risk'], 2) if r.get('risk', 0) > 0 else 0
        return r


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tw = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
    
    def show(self, e=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tw, text=self.text, bg="#1e293b", fg="#e2e8f0",
                font=("Segoe UI", 9), padx=10, pady=5, relief=tk.SOLID, bd=1).pack()
    
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
        self.min_liquidity_cr = self._load_app_settings().get('min_liquidity_cr', DEFAULT_MIN_LIQUIDITY_CR)
        self.build_ui()
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.refresh_watchlist()
        self.center()
        self._setup_market_status()
        self.root.after(30000, self._check_auto_report)
        logger.info("App started v7.0")
    
    def center(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        self.root.geometry(f"{w}x{h}+{(self.root.winfo_screenwidth()-w)//2}+{(self.root.winfo_screenheight()-h)//2}")
    
    def btn(self, parent, text, color, cmd, **kw):
        b = tk.Button(parent, text=text, bg=color, fg='white', font=('Segoe UI', 10, 'bold'),
                     relief=tk.FLAT, padx=14, pady=6, command=cmd, cursor='hand2', **kw)
        lighter = self.lighten(color, 0.15)
        b.bind("<Enter>", lambda e: b.configure(bg=lighter))
        b.bind("<Leave>", lambda e: b.configure(bg=color))
        return b
    
    def lighten(self, color, factor=0.15):
        try:
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            r = max(0, min(255, int(r + (255 if factor > 0 else 0) * factor)))
            g = max(0, min(255, int(g + (255 if factor > 0 else 0) * factor)))
            b = max(0, min(255, int(b + (255 if factor > 0 else 0) * factor)))
            return f'#{r:02x}{g:02x}{b:02x}'
        except: return color
    
    def build_ui(self):
        T = THEME
        
        # HEADER - Premium dark theme with gradient effect
        header = tk.Frame(self.root, bg=T['bg2'], height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        # Accent line at top
        accent_line = tk.Frame(self.root, bg=T['accent'], height=3)
        accent_line.pack(fill=tk.X)
        accent_line.lift()
        
        # Logo
        logo_frame = tk.Frame(header, bg=T['bg2'])
        logo_frame.pack(side=tk.LEFT, padx=20)
        
        try:
            if LOGO_PATH.exists() and PIL_OK:
                img = Image.open(str(LOGO_PATH))
                img = img.resize((55, 55), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
                logo_lbl = tk.Label(logo_frame, image=self.logo_img, bg=T['bg2'])
                logo_lbl.pack(side=tk.LEFT, padx=(0, 12))
        except: pass
        
        title_frame = tk.Frame(header, bg=T['bg2'])
        title_frame.pack(side=tk.LEFT)
        
        tk.Label(title_frame, text="DR. NILESH SHAH'S MARKET ANALYSIS", bg=T['bg2'], fg=T['gold'],
                font=('Segoe UI', 22, 'bold')).pack(anchor=tk.W)
        tk.Label(title_frame, text="Professional Technical Scanner  |  2-Year Daily Analysis  |  v7.0", bg=T['bg2'], fg=T['fg3'],
                font=('Segoe UI', 10)).pack(anchor=tk.W)
        
        # Market status indicator (right side)
        market_frame = tk.Frame(header, bg=T['bg2'])
        market_frame.pack(side=tk.RIGHT, padx=20)
        
        self.market_dot = tk.Canvas(market_frame, width=12, height=12, bg=T['bg2'], highlightthickness=0)
        self.market_dot.pack(side=tk.LEFT, padx=(0, 5))
        self.market_dot.create_oval(2, 2, 10, 10, fill=T['danger'], outline='')
        self.market_status_lbl = tk.Label(market_frame, text="MARKET CLOSED", bg=T['bg2'], fg=T['fg3'],
                font=('Segoe UI', 9, 'bold'))
        self.market_status_lbl.pack(side=tk.LEFT)
        
        # Buttons row
        btn_row = tk.Frame(header, bg=T['bg2'])
        btn_row.pack(side=tk.RIGHT, padx=10)
        
        self.btn(btn_row, "Import", T['accent3'], self.import_list).pack(side=tk.RIGHT, padx=3)
        self.btn(btn_row, "Save", T['success'], self.save_list).pack(side=tk.RIGHT, padx=3)
        self.btn(btn_row, "Excel", '#059669', self.export_results).pack(side=tk.RIGHT, padx=3)
        self.btn(btn_row, "PDF", '#7c3aed', self.export_pdf).pack(side=tk.RIGHT, padx=3)
        self.btn(btn_row, "Report", T['gold'], self.generate_daily_report).pack(side=tk.RIGHT, padx=3)
        self.btn(btn_row, "Email", T['danger'], self.send_email_report).pack(side=tk.RIGHT, padx=3)
        
        # DASHBOARD
        self.dash_frame = tk.Frame(self.root, bg=T['bg'])
        self.dash_frame.pack(fill=tk.X, padx=15, pady=10)
        
        self.dash_cards = {}
        cards = [
            ('total', 'TOTAL', '0', T['accent'], T['accent']),
            ('sb', 'STRONG BUY', '0', '#059669', '#065f46'),
            ('buy', 'BUY', '0', T['success'], '#064e3b'),
            ('hold', 'HOLD', '0', T['warning'], '#78350f'),
            ('sell', 'SELL', '0', T['danger2'], '#7f1d1d'),
            ('ss', 'STRONG SELL', '0', T['danger'], '#450a0a'),
            ('avg', 'AVG SCORE', '0', T['gold'], '#713f12'),
        ]
        
        for key, label, val, color, border_color in cards:
            card = tk.Frame(self.dash_frame, bg=T['card'], highlightbackground=border_color, highlightthickness=1, padx=18, pady=10)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
            tk.Label(card, text=label, bg=T['card'], fg=T['fg3'], font=('Segoe UI', 8, 'bold')).pack()
            val_lbl = tk.Label(card, text=val, bg=T['card'], fg=color, font=('Segoe UI', 26, 'bold'))
            val_lbl.pack()
            self.dash_cards[key] = val_lbl
        
        # CONTROLS
        ctrl = tk.Frame(self.root, bg=T['bg2'], highlightbackground=T['border'], highlightthickness=1)
        ctrl.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        # Watchlist
        wl = tk.LabelFrame(ctrl, text=" Watchlist ", bg=T['bg2'], fg=T['accent'], font=('Segoe UI', 10, 'bold'), bd=0)
        wl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        entry_row = tk.Frame(wl, bg=T['bg2'])
        entry_row.pack(fill=tk.X, padx=8, pady=4)
        
        tk.Label(entry_row, text="Symbol:", bg=T['bg2'], fg=T['fg'], font=('Segoe UI', 10)).pack(side=tk.LEFT)
        self.entry = tk.Entry(entry_row, font=('Segoe UI', 12, 'bold'), bg=T['input'], fg=T['fg'],
                            insertbackground=T['fg'], relief=tk.FLAT, width=14, highlightbackground=T['border'], highlightthickness=1)
        self.entry.pack(side=tk.LEFT, padx=8)
        self.entry.bind('<Return>', lambda e: self.add_stock())
        Tooltip(self.entry, "Enter NSE symbol (e.g., RELIANCE, TCS, INFY)")
        
        btn_row = tk.Frame(wl, bg=T['bg2'])
        btn_row.pack(fill=tk.X, padx=8, pady=4)
        
        self.btn(btn_row, "Add", T['success'], self.add_stock).pack(side=tk.LEFT, padx=3)
        self.btn(btn_row, "Delete", T['danger'], self.del_stock).pack(side=tk.LEFT, padx=3)
        self.btn(btn_row, "Clear", T['warning'], self.clear_list).pack(side=tk.LEFT, padx=3)
        
        tk.Label(btn_row, text=" Sector:", bg=T['bg2'], fg=T['fg3'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(15, 5))
        self.sector_var = tk.StringVar(value="All")
        sector_cb = ttk.Combobox(btn_row, textvariable=self.sector_var, values=["All"] + list(SECTOR_MAP.keys()), state='readonly', width=12)
        sector_cb.pack(side=tk.LEFT)
        sector_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_watchlist())
        Tooltip(sector_cb, "Filter watchlist by sector")
        
        # Scan
        scan = tk.LabelFrame(ctrl, text=" Scan ", bg=T['bg2'], fg=T['danger'], font=('Segoe UI', 10, 'bold'), bd=0)
        scan.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        scan_row = tk.Frame(scan, bg=T['bg2'])
        scan_row.pack(fill=tk.X, padx=8, pady=8)
        
        self.scan_btn = self.btn(scan_row, "SCAN ALL STOCKS", T['danger'], self.start_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=8)
        Tooltip(self.scan_btn, "Scan all stocks (F5)")
        
        self.progress = ttk.Progressbar(scan_row, mode='determinate', length=150)
        self.progress.pack(side=tk.LEFT, padx=8)
        
        self.status_lbl = tk.Label(scan_row, text="Ready", bg=T['bg2'], fg=T['fg3'], font=('Segoe UI', 9))
        self.status_lbl.pack(side=tk.LEFT, padx=8)
        
        # NOTEBOOK
        nb_frame = tk.Frame(self.root, bg=T['bg'])
        nb_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 5))
        
        self.nb = ttk.Notebook(nb_frame)
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
        
        # STATUS BAR
        status = tk.Frame(self.root, bg=T['bg3'], height=30)
        status.pack(fill=tk.X)
        status.pack_propagate(False)
        
        tk.Label(status, text=f"Last Scan: Never", bg=T['bg3'], fg=T['fg3'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=15)
        self.last_scan_lbl = status.winfo_children()[-1]
        tk.Label(status, text=f"Cache: {self.analyzer.cache.count()}", bg=T['bg3'], fg=T['fg3'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=15)
        tk.Label(status, text="F5=Scan | Ctrl+I=Import | Del=Delete", bg=T['bg3'], fg=T['fg3'], font=('Segoe UI', 9)).pack(side=tk.RIGHT, padx=15)
        
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
    
    def build_watchlist_tab(self):
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Watchlist  ")
        
        # Groups bar
        groups_bar = tk.Frame(tab, bg=T['bg2'], height=38)
        groups_bar.pack(fill=tk.X)
        groups_bar.pack_propagate(False)
        
        tk.Label(groups_bar, text="GROUP:", bg=T['bg2'], fg=T['fg3'], font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=10)
        self.group_var = tk.StringVar(value='All Stocks')
        self.group_cb = ttk.Combobox(groups_bar, textvariable=self.group_var, 
                                     values=list(self.watchlist_groups.keys()), state='readonly', width=15)
        self.group_cb.pack(side=tk.LEFT, padx=5)
        self.group_cb.bind('<<ComboboxSelected>>', lambda e: self._switch_group())
        self.btn(groups_bar, "New Group", T['accent'], self._create_group).pack(side=tk.LEFT, padx=4)
        self.btn(groups_bar, "Add to Group", T['success'], self._add_to_group).pack(side=tk.LEFT, padx=4)
        self.btn(groups_bar, "Remove", T['warning'], self._remove_from_group).pack(side=tk.LEFT, padx=4)
        self.group_count_lbl = tk.Label(groups_bar, text="", bg=T['bg2'], fg=T['fg3'], font=('Segoe UI', 9))
        self.group_count_lbl.pack(side=tk.RIGHT, padx=10)
        
        # Main list
        list_frame = tk.Frame(tab, bg=T['bg'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        sb = tk.Scrollbar(list_frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.wl_list = tk.Listbox(list_frame, bg=T['input'], fg=T['accent2'], font=('Consolas', 14),
                                 selectbackground=T['accent'], selectforeground='white', relief=tk.FLAT, yscrollcommand=sb.set,
                                 highlightbackground=T['border'], highlightthickness=1)
        self.wl_list.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.wl_list.yview)
        self.wl_count = tk.Label(tab, text="Stocks: 0", bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 10))
        self.wl_count.pack(pady=5)

    def build_results_tab(self):
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Scan Results  ")
        
        cols = ('Symbol', 'Price', 'Change%', 'RSI', 'SuperTrend', 'VWAP', 'Score', 'Recommendation', '52W High', '52W Low', 'ATR',
                'Traded/day (Cr)')
        
        # Search bar above results
        search_frame = tk.Frame(tab, bg=T['bg'])
        search_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        tk.Label(search_frame, text="Search:", bg=T['bg'], fg=T['fg'], font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *args: self.filter_results())  # trace('w') was removed in Tk 9
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, bg=T['input'], fg=T['fg'],
                                     font=('Segoe UI', 10), width=30, relief=tk.FLAT,
                                     highlightbackground=T['border'], highlightthickness=1)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        Tooltip(self.search_entry, "Type to filter results by symbol")
        
        self.btn(search_frame, "Clear", T['bg3'], lambda: self.search_var.set("")).pack(side=tk.LEFT, padx=5)
        
        tk.Label(search_frame, text="Filter:", bg=T['bg'], fg=T['fg'], font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=(20, 5))
        self.result_filter_var = tk.StringVar(value="All")
        filter_cb = ttk.Combobox(search_frame, textvariable=self.result_filter_var,
                                values=["All", "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"],
                                state='readonly', width=15)
        filter_cb.pack(side=tk.LEFT, padx=5)
        filter_cb.bind("<<ComboboxSelected>>", lambda e: self.filter_results())

        self.hide_illiquid_var = tk.BooleanVar(value=False)
        self.hide_illiquid_cb = tk.Checkbutton(search_frame, variable=self.hide_illiquid_var, command=self.filter_results,
                                               text=f"Hide illiquid (< Rs {self.min_liquidity_cr:g} Cr/day)",
                                               bg=T['bg'], fg=T['fg'], selectcolor=T['bg3'], activebackground=T['bg'],
                                               font=('Segoe UI', 10))
        self.hide_illiquid_cb.pack(side=tk.LEFT, padx=(20, 5))
        Tooltip(self.hide_illiquid_cb, "Illiquid stocks: stop-loss and targets are unreliable because\n"
                                       "prices can gap and orders may not fill. Threshold is set in Settings.")
        
        frame = tk.Frame(tab, bg=T['bg'])
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        sy = tk.Scrollbar(frame)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        sx = tk.Scrollbar(frame, orient=tk.HORIZONTAL)
        sx.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tree = ttk.Treeview(frame, columns=cols, show='headings', yscrollcommand=sy.set, xscrollcommand=sx.set)
        for c in cols:
            self.tree.heading(c, text=c, anchor=tk.CENTER, command=lambda c=c: self.sort_tree(c))
            self.tree.column(c, width=110, anchor=tk.CENTER)
        
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
        canvas.create_window((0, 0), window=frame, anchor="nw")
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
        tk.Label(self.bd_frame, text="Double-click a stock to view breakdown",
                bg=THEME['bg'], fg=THEME['accent'], font=('Segoe UI', 14, 'bold')).pack(pady=50)
    
    def build_targets_tab(self):
        self.tg_frame = self.build_scrollable_tab("Stop-Loss & Targets")
        tk.Label(self.tg_frame, text="Double-click a stock to view targets",
                bg=THEME['bg'], fg=THEME['accent'], font=('Segoe UI', 14, 'bold')).pack(pady=50)
    
    def build_patterns_tab(self):
        self.pt_frame = self.build_scrollable_tab("Pattern Analysis")
        tk.Label(self.pt_frame, text="Double-click a stock to view detected patterns",
                bg=THEME['bg'], fg=THEME['accent'], font=('Segoe UI', 14, 'bold')).pack(pady=50)
    

    def build_corporate_tab(self):
        """Build Corporate Actions tab - comprehensive scanner with live NSE/BSE data."""
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Corporate Actions  ")

        # Header
        header = tk.Frame(tab, bg=T['bg2'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="Corporate Actions Scanner (NSE + BSE Live Data)",
                bg=T['bg2'], fg=T['gold'], font=('Segoe UI', 14, 'bold')).pack(side=tk.LEFT, padx=15)

        self.btn(header, "Export CSV", T['success'], self.export_corporate_csv).pack(side=tk.RIGHT, padx=5)
        self.btn(header, "View Details", T['accent'], self.show_corporate_popup).pack(side=tk.RIGHT, padx=5)
        self.btn(header, "SCAN ALL", T['danger'], self.load_corporate_actions).pack(side=tk.RIGHT, padx=5)

        # Stats bar
        stats_bar = tk.Frame(tab, bg=T['bg3'], height=35)
        stats_bar.pack(fill=tk.X)
        stats_bar.pack_propagate(False)

        self.corp_stats_labels = {}
        for key, label, color in [('total', 'Total', T['accent']), ('upcoming', 'Upcoming', T['success']),
                                   ('dividends', 'Dividends', T['gold']), ('splits', 'Splits', T['warning']),
                                   ('bonus', 'Bonus', '#10b981')]:
            frame = tk.Frame(stats_bar, bg=T['bg3'])
            frame.pack(side=tk.LEFT, padx=15)
            tk.Label(frame, text=label, bg=T['bg3'], fg=T['fg3'], font=('Segoe UI', 8)).pack(side=tk.LEFT)
            lbl = tk.Label(frame, text="0", bg=T['bg3'], fg=color, font=('Segoe UI', 11, 'bold'))
            lbl.pack(side=tk.LEFT, padx=5)
            self.corp_stats_labels[key] = lbl

        self.corp_source_lbl = tk.Label(stats_bar, text="Source: -", bg=T['bg3'], fg=T['fg3'], font=('Segoe UI', 8))
        self.corp_source_lbl.pack(side=tk.RIGHT, padx=15)

        # Main content - PanedWindow
        content = tk.PanedWindow(tab, orient=tk.HORIZONTAL, bg=T['bg'])
        content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # LEFT - Stock list
        left = tk.LabelFrame(content, text=" Watchlist ", bg=T['bg'], fg=T['accent'], font=('Segoe UI', 10, 'bold'))
        content.add(left, width=220)

        self.corp_listbox = tk.Listbox(left, bg=T['input'], fg=T['accent2'], font=('Consolas', 11),
                                       selectbackground=T['accent'], selectforeground='white', width=22)
        self.corp_listbox.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self.corp_listbox.bind('<Double-1>', lambda e: self.show_corporate_popup())

        # RIGHT - Actions table
        right = tk.Frame(content, bg=T['bg'])
        content.add(right)

        # Filter bar
        filter_bar = tk.Frame(right, bg=T['bg2'])
        filter_bar.pack(fill=tk.X, pady=(0, 3))

        tk.Label(filter_bar, text="Show:", bg=T['bg2'], fg=T['fg'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        self.corp_filter_var = tk.StringVar(value="All")
        for val in ["All", "Upcoming", "Past", "Dividends", "Splits", "Bonus", "Rights", "Buyback"]:
            tk.Radiobutton(filter_bar, text=val, variable=self.corp_filter_var, value=val,
                          bg=T['bg2'], fg=T['fg'], selectcolor=T['bg3'], font=('Segoe UI', 8),
                          command=self._filter_corporate_actions).pack(side=tk.LEFT, padx=2)

        # Actions Treeview
        tree_frame = tk.Frame(right, bg=T['bg'])
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ('Symbol', 'Company', 'Type', 'Action', 'Amount', 'Ex-Date', 'Record Date', 'Days', 'Status', 'Source')
        sy = tk.Scrollbar(tree_frame)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        sx = tk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
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
        self.corp_tree.tag_configure('upcoming', background='#064e3b', foreground='#6ee7b7')
        self.corp_tree.tag_configure('today', background='#7f1d1d', foreground='#fca5a5')
        self.corp_tree.tag_configure('past', background='#1f2937', foreground='#6b7280')

        # Status bar
        self.corp_status = tk.Label(tab, text="Click 'SCAN ALL' to fetch live corporate actions from NSE & BSE",
                                   bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 10))
        self.corp_status.pack(pady=5)

        # Internal state
        self.corp_engine = None
        self.corporate_data = {}      # symbol -> engine data dict
        self._corp_symbol_map = {}    # listbox display -> symbol

    def load_corporate_actions(self):
        """Scan ALL watchlist stocks for corporate actions using the engine."""
        if not self.watchlist:
            messagebox.showwarning("Warning", "Watchlist is empty!")
            return

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

        # Header
        hdr = tk.Frame(popup, bg=T['bg2'], height=55)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        company_name = data.get('company', data.get('name', symbol))
        tk.Label(hdr, text=f"{symbol}  -  {company_name}",
                bg=T['bg2'], fg=T['gold'], font=('Segoe UI', 16, 'bold')).pack(side=tk.LEFT, padx=15)

        # Content - scrollable text
        content = tk.Frame(popup, bg=T['bg'])
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_scroll = tk.Scrollbar(content)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        text = tk.Text(content, bg=T['input'], fg=T['fg'], font=('Consolas', 11),
                       wrap=tk.WORD, yscrollcommand=text_scroll.set, padx=10, pady=10)
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
        """Build Charts tab."""
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Charts  ")
        
        header = tk.Frame(tab, bg=T['bg2'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="Stock Charts", bg=T['bg2'], fg=T['gold'],
                font=('Segoe UI', 14, 'bold')).pack(side=tk.LEFT, padx=15)
        
        self.chart_period_var = tk.StringVar(value="6mo")
        for label, val in [("1M", "1mo"), ("3M", "3mo"), ("6M", "6mo"), ("1Y", "1y"), ("2Y", "2y")]:
            tk.Radiobutton(header, text=label, variable=self.chart_period_var, value=val,
                          bg=T['bg2'], fg=T['fg'], selectcolor=T['bg3'],
                          font=('Segoe UI', 9)).pack(side=tk.RIGHT, padx=3)
        
        tk.Label(header, text="Period:", bg=T['bg2'], fg=T['fg'],
                font=('Segoe UI', 10)).pack(side=tk.RIGHT, padx=5)
        
        self.btn(header, "Show Chart", T['accent'], self.show_stock_chart).pack(side=tk.RIGHT, padx=10)
        
        self.chart_frame = tk.Frame(tab, bg=T['bg'])
        self.chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        if not MATPLOTLIB_OK:
            tk.Label(self.chart_frame, text="Install matplotlib for charts:\npip install matplotlib",
                    bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 14)).pack(pady=50)
        else:
            tk.Label(self.chart_frame, text="Select a stock and click 'Show Chart'",
                    bg=T['bg'], fg=T['accent'], font=('Segoe UI', 14, 'bold')).pack(pady=50)
    
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

        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        loading = tk.Label(self.chart_frame, text=f"Loading {symbol}...",
                bg=THEME['bg'], fg=THEME['fg'], font=('Segoe UI', 12))
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
            loading.configure(text=msg, fg=THEME['danger'])
            messagebox.showerror("Error", msg)

        def render(df):
            try:
                if df is None or df.empty:
                    fail(f"No data for {symbol}")
                    return

                loading.destroy()
                fig = Figure(figsize=(14, 8), dpi=100, facecolor='#0a0e1a')
                
                ax1 = fig.add_subplot(211)
                ax1.set_facecolor('#162033')
                ax1.plot(df.index, df['Close'], color='#00d4ff', linewidth=1.5, label='Close')
                
                if len(df) >= 20:
                    ax1.plot(df.index, df['Close'].rolling(20).mean(), color='#fbbf24', linewidth=1, label='SMA 20')
                if len(df) >= 50:
                    ax1.plot(df.index, df['Close'].rolling(50).mean(), color='#ff6b6b', linewidth=1, label='SMA 50')
                
                ax1.set_title(f'{symbol} ({period})', color='#fbbf24', fontsize=14)
                ax1.legend(fontsize=8)
                ax1.grid(True, alpha=0.3)
                ax1.tick_params(colors='#8892b0')
                
                ax2 = fig.add_subplot(212, sharex=ax1)
                ax2.set_facecolor('#162033')
                colors_v = ['#00b894' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ff6b6b' for i in range(len(df))]
                ax2.bar(df.index, df['Volume'], color=colors_v, alpha=0.7)
                ax2.set_ylabel('Volume', color='#8892b0')
                ax2.grid(True, alpha=0.3)
                ax2.tick_params(colors='#8892b0')
                
                fig.tight_layout()
                
                canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            except Exception as e:
                fail(str(e))

        threading.Thread(target=fetch, daemon=True).start()
    
    def build_sector_tab(self):
        """Build Sector Analysis tab."""
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Sector  ")
        
        header = tk.Frame(tab, bg=T['bg2'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="Sector Analysis", bg=T['bg2'], fg=T['gold'],
                font=('Segoe UI', 14, 'bold')).pack(side=tk.LEFT, padx=15)
        self.btn(header, "Analyze", T['accent'], self.analyze_sectors).pack(side=tk.RIGHT, padx=10)
        
        cols = ('Sector', 'Stocks', 'Avg Score', 'Buy', 'Hold', 'Sell', 'Best', 'Rotation', 'Rank')
        self.sector_tree = ttk.Treeview(tab, columns=cols, show='headings', height=15)
        
        widths = {'Sector': 100, 'Stocks': 60, 'Avg Score': 80, 'Buy': 50, 'Hold': 50,
                  'Sell': 50, 'Best': 90, 'Rotation': 110, 'Rank': 50}
        for col in cols:
            self.sector_tree.heading(col, text=col, anchor=tk.CENTER)
            self.sector_tree.column(col, width=widths.get(col, 90), anchor=tk.CENTER)
        
        self.sector_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.sector_status = tk.Label(tab, text="Click 'Analyze' after scanning stocks",
                                     bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 10))
        self.sector_status.pack(pady=5)
    
    def analyze_sectors(self):
        """Analyze sectors with rotation signals."""
        if not self.results:
            messagebox.showinfo("Info", "Scan stocks first!")
            return
        
        for item in self.sector_tree.get_children():
            self.sector_tree.delete(item)
        
        sector_data = {}
        for r in self.results:
            for sector, stocks in SECTOR_MAP.items():
                if r['symbol'] in stocks:
                    sector_data.setdefault(sector, []).append(r)
                    break
        
        sector_scores = []
        for sector, stocks in sector_data.items():
            n = len(stocks)
            avg = sum(s['score'] for s in stocks) / n
            sector_scores.append((sector, avg, stocks))
        sector_scores.sort(key=lambda x: x[1], reverse=True)
        
        spread = sector_scores[0][1] - sector_scores[-1][1] if len(sector_scores) >= 2 else 0
        
        for rank, (sector, avg, stocks) in enumerate(sector_scores):
            n = len(stocks)
            buy = sum(1 for s in stocks if s['rec'] in ['STRONG BUY', 'BUY'])
            hold = sum(1 for s in stocks if s['rec'] == 'HOLD')
            sell = sum(1 for s in stocks if s['rec'] in ['SELL', 'STRONG SELL'])
            srt = sorted(stocks, key=lambda x: x['score'], reverse=True)
            
            if avg >= 65:
                rotation = "LEADING"
            elif avg >= 50:
                rotation = "IMPROVING"
            elif avg >= 40:
                rotation = "WEAKENING"
            else:
                rotation = "LAGGING"
            
            self.sector_tree.insert('', tk.END, values=(
                sector, n, f"{avg:.1f}", buy, hold, sell,
                srt[0]['symbol'] if srt else 'N/A',
                rotation, f"#{rank+1}"
            ))
        
        if sector_scores:
            self.sector_status.configure(
                text=f"Rotation: {sector_scores[0][0]} LEADING ({sector_scores[0][1]:.1f}) | "
                     f"{sector_scores[-1][0]} LAGGING ({sector_scores[-1][1]:.1f}) | Spread: {spread:.1f} pts")
    
    def build_backtest_tab(self):
        """Build Backtest tab: does the score actually predict returns on these stocks?"""
        T = THEME
        tab = tk.Frame(self.nb, bg=T['bg'])
        self.nb.add(tab, text="  Backtest  ")

        header = tk.Frame(tab, bg=T['bg2'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Strategy Backtest", bg=T['bg2'], fg=T['gold'],
                 font=('Segoe UI', 14, 'bold')).pack(side=tk.LEFT, padx=15)

        self.bt_apply_btn = self.btn(header, "Apply Suggested Weights", T['success'], self.apply_suggested_weights)
        self.bt_apply_btn.pack(side=tk.RIGHT, padx=10)
        self.bt_apply_btn.configure(state=tk.DISABLED)
        self.bt_run_btn = self.btn(header, "Run Backtest", T['accent'], self.run_backtest)
        self.bt_run_btn.pack(side=tk.RIGHT, padx=5)

        self.bt_horizon_var = tk.StringVar(value="10 days")
        ttk.Combobox(header, textvariable=self.bt_horizon_var, values=["5 days", "10 days", "20 days"],
                     state='readonly', width=8).pack(side=tk.RIGHT, padx=5)
        tk.Label(header, text="Hold for:", bg=T['bg2'], fg=T['fg'], font=('Segoe UI', 10)).pack(side=tk.RIGHT)
        self.bt_history_var = tk.StringVar(value="5 years")
        ttk.Combobox(header, textvariable=self.bt_history_var, values=["2 years", "3 years", "5 years"],
                     state='readonly', width=8).pack(side=tk.RIGHT, padx=(5, 15))
        tk.Label(header, text="History:", bg=T['bg2'], fg=T['fg'], font=('Segoe UI', 10)).pack(side=tk.RIGHT)
        self.bt_liquid_var = tk.BooleanVar(value=False)
        self.bt_liquid_cb = tk.Checkbutton(header, variable=self.bt_liquid_var,
                                           text=f"Liquid stocks only (>= Rs {self.min_liquidity_cr:g} Cr/day)",
                                           bg=T['bg2'], fg=T['fg'], selectcolor=T['bg3'], activebackground=T['bg2'],
                                           font=('Segoe UI', 9))
        self.bt_liquid_cb.pack(side=tk.RIGHT, padx=10)

        self.bt_status = tk.Label(tab, text="Tests the scoring system on your watchlist's past prices: for every past day it "
                                            "scores each stock exactly like a scan would, then checks what the price did next.",
                                  bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 10), wraplength=1300, justify=tk.LEFT)
        self.bt_status.pack(anchor=tk.W, padx=15, pady=(8, 2))
        self.bt_summary = tk.Label(tab, text="", bg=T['bg'], fg=T['fg'], font=('Segoe UI', 11, 'bold'),
                                   wraplength=1300, justify=tk.LEFT)
        self.bt_summary.pack(anchor=tk.W, padx=15, pady=(2, 6))

        tables = tk.Frame(tab, bg=T['bg'])
        tables.pack(fill=tk.BOTH, expand=True, padx=10)

        # Left: performance by recommendation
        left = tk.LabelFrame(tables, text=" What happened after each signal (newer 40% of history) ", bg=T['bg'],
                             fg=T['accent'], font=('Segoe UI', 10, 'bold'))
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        cols = ('Weights', 'Signal', 'Times', 'Avg Return', 'Win Rate', 'vs Avg')
        self.bt_bucket_tree = ttk.Treeview(left, columns=cols, show='headings', height=11)
        for c, w in zip(cols, (80, 100, 65, 85, 75, 75)):
            self.bt_bucket_tree.heading(c, text=c, anchor=tk.CENTER)
            self.bt_bucket_tree.column(c, width=w, anchor=tk.CENTER)
        self.bt_bucket_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.bt_bucket_tree.tag_configure('good', foreground='#34d399')
        self.bt_bucket_tree.tag_configure('bad', foreground='#f87171')

        # Right: each indicator's predictive power
        right = tk.LabelFrame(tables, text=" Which indicators actually help ", bg=T['bg'],
                              fg=T['accent'], font=('Segoe UI', 10, 'bold'))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        cols = ('Indicator', 'Current Wt', 'Power (older)', 'Power (newer)', 'Suggested Wt', 'Verdict')
        self.bt_ind_tree = ttk.Treeview(right, columns=cols, show='headings', height=11)
        for c, w in zip(cols, (105, 80, 95, 95, 90, 90)):
            self.bt_ind_tree.heading(c, text=c, anchor=tk.CENTER)
            self.bt_ind_tree.column(c, width=w, anchor=tk.CENTER)
        self.bt_ind_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.bt_ind_tree.tag_configure('good', foreground='#34d399')
        self.bt_ind_tree.tag_configure('bad', foreground='#f87171')

        tk.Label(tab, text="Power = rank correlation between the indicator's score and the next-period return "
                           "(above 0 = higher score was followed by better returns; 0.03+ is meaningful for daily stock data).  "
                           "Suggested weights are learned on the OLDER 60% of history and judged on the NEWER 40%, "
                           "so the comparison is honest. Past results don't guarantee future returns; daily signals overlap, "
                           "and delisted stocks aren't included.",
                 bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 8), wraplength=1300, justify=tk.LEFT).pack(anchor=tk.W, padx=15, pady=6)

        self._bt_result = None
        self._bt_cache = None   # (key, samples, skipped) - reused when only the holding period changes

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
        self._set_weights(dict(w))
        messagebox.showinfo("Applied", "Suggested weights applied and saved.\n\nRe-scan (F5) to see updated scores.")
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
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._scroll_canvases.append(canvas)

        # Header
        header = tk.Frame(content, bg=T['bg2'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Settings & Configuration", bg=T['bg2'], fg=T['gold'],
                font=('Segoe UI', 14, 'bold')).pack(side=tk.LEFT, padx=15)
        
        # ===== EMAIL CONFIGURATION =====
        email_frame = tk.LabelFrame(content, text=" Email Report Configuration ", 
                                    bg=T['bg'], fg=T['accent'], font=('Segoe UI', 11, 'bold'))
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
                    font=('Segoe UI', 10), width=18, anchor=tk.W).pack(side=tk.LEFT)
            
            var = tk.StringVar(value=default)
            self.email_vars[key] = var
            
            show = '*' if 'password' in key.lower() else ''
            entry = tk.Entry(row, textvariable=var, bg=T['input'], fg=T['fg'],
                           font=('Segoe UI', 10), width=40, show=show,
                           relief=tk.FLAT, highlightbackground=T['border'], highlightthickness=1)
            entry.pack(side=tk.LEFT, padx=5)
            
            # Store password entry reference for toggle
            if key == 'sender_password':
                self.pw_entry = entry
                self.pw_visible = False
                self.btn(row, "👁", T['bg3'], self.toggle_password_visibility).pack(side=tk.LEFT, padx=2)
        
        # Load existing config into fields
        self._load_email_config_to_fields()
        
        email_btn_frame = tk.Frame(email_frame, bg=T['bg'])
        email_btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.btn(email_btn_frame, "Save Email Config", T['success'], self.save_email_config).pack(side=tk.LEFT, padx=5)
        self.btn(email_btn_frame, "Test Email", T['accent'], self.test_email).pack(side=tk.LEFT, padx=5)
        self.btn(email_btn_frame, "Send Report Now", T['warning'], self.send_email_report).pack(side=tk.LEFT, padx=5)
        self.btn(email_btn_frame, "Clear Config", T['danger'], self.clear_email_config).pack(side=tk.LEFT, padx=5)
        
        # Email help text
        help_frame = tk.Frame(email_frame, bg=T['bg'])
        help_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(help_frame, text="📧 Gmail Setup Guide:", bg=T['bg'], fg=T['gold'], font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W)
        tk.Label(help_frame, text="1. Enable 2-Factor Authentication on your Google Account", bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 9)).pack(anchor=tk.W, padx=10)
        tk.Label(help_frame, text="2. Go to: https://myaccount.google.com/apppasswords", bg=T['bg'], fg=T['accent'], font=('Segoe UI', 9)).pack(anchor=tk.W, padx=10)
        tk.Label(help_frame, text="3. Generate App Password for 'Mail' → Use that 16-char password above", bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 9)).pack(anchor=tk.W, padx=10)
        tk.Label(help_frame, text="4. Port 587 = STARTTLS (recommended) | Port 465 = SSL", bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 9)).pack(anchor=tk.W, padx=10)
        
        # Email status indicator
        self.email_status_lbl = tk.Label(email_frame, text="", bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 9))
        self.email_status_lbl.pack(anchor=tk.W, padx=10, pady=5)
        self._update_email_status()
        
        # ===== AUTO REPORT SCHEDULING =====
        schedule_frame = tk.LabelFrame(content, text=" Auto Report Scheduling ", 
                                       bg=T['bg'], fg=T['accent'], font=('Segoe UI', 11, 'bold'))
        schedule_frame.pack(fill=tk.X, padx=20, pady=10)
        
        sched = self._load_schedule_config()
        self.auto_report_var = tk.BooleanVar(value=sched['enabled'])
        tk.Checkbutton(schedule_frame, text="Enable Auto-Report Email", 
                      variable=self.auto_report_var,
                      bg=T['bg'], fg=T['fg'], selectcolor=T['bg3'],
                      font=('Segoe UI', 10)).pack(anchor=tk.W, padx=10, pady=5)
        
        sched_row = tk.Frame(schedule_frame, bg=T['bg'])
        sched_row.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(sched_row, text="Send Time:", bg=T['bg'], fg=T['fg'],
                font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=5)
        
        self.report_hour_var = tk.StringVar(value=str(sched['hour']))
        ttk.Combobox(sched_row, textvariable=self.report_hour_var,
                    values=[str(h) for h in range(24)], state='readonly', width=5).pack(side=tk.LEFT)
        tk.Label(sched_row, text=":", bg=T['bg'], fg=T['fg'], font=('Segoe UI', 10)).pack(side=tk.LEFT)
        
        self.report_min_var = tk.StringVar(value=f"{sched['minute']:02d}")
        ttk.Combobox(sched_row, textvariable=self.report_min_var,
                    values=[f"{m:02d}" for m in range(0, 60, 5)], state='readonly', width=5).pack(side=tk.LEFT)
        
        tk.Label(sched_row, text="(24-hour format)", bg=T['bg'], fg=T['fg3'],
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=10)
        
        type_row = tk.Frame(schedule_frame, bg=T['bg'])
        type_row.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(type_row, text="Report Type:", bg=T['bg'], fg=T['fg'],
                font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=5)
        
        self.report_type_var = tk.StringVar(value=sched['report_type'])
        ttk.Combobox(type_row, textvariable=self.report_type_var,
                    values=["Indian Only", "Indian + US", "US Only"], state='readonly', width=15).pack(side=tk.LEFT)
        
        sched_btns = tk.Frame(schedule_frame, bg=T['bg'])
        sched_btns.pack(fill=tk.X, padx=10, pady=(10, 2))
        self.btn(sched_btns, "Save Schedule", T['success'], self.save_schedule).pack(side=tk.LEFT, padx=(0, 5))
        self.btn(sched_btns, "Install Windows Task", T['accent'], self.install_windows_task).pack(side=tk.LEFT, padx=5)
        self.btn(sched_btns, "Remove Windows Task", T['danger'], self.remove_windows_task).pack(side=tk.LEFT, padx=5)

        self.task_status_lbl = tk.Label(schedule_frame, text="Windows task: checking...", bg=T['bg'], fg=T['fg3'],
                                        font=('Segoe UI', 9))
        self.task_status_lbl.pack(anchor=tk.W, padx=10, pady=(2, 2))
        tk.Label(schedule_frame, text="The Windows task emails the report on NSE trading days even when this app is closed "
                                      "(weekends & NSE holidays are skipped; sent at most once a day).",
                 bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 8)).pack(anchor=tk.W, padx=10, pady=(0, 10))
        self.root.after(1500, self._update_task_status)
        
        # ===== LIQUIDITY =====
        liq_frame = tk.LabelFrame(content, text=" Liquidity Filter ",
                                  bg=T['bg'], fg=T['accent'], font=('Segoe UI', 11, 'bold'))
        liq_frame.pack(fill=tk.X, padx=20, pady=10)
        liq_row = tk.Frame(liq_frame, bg=T['bg'])
        liq_row.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(liq_row, text="Flag stocks trading less than Rs", bg=T['bg'], fg=T['fg'],
                 font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=(5, 5))
        self.min_liquidity_var = tk.StringVar(value=f"{self.min_liquidity_cr:g}")
        tk.Spinbox(liq_row, from_=0, to=1000, increment=0.5, textvariable=self.min_liquidity_var, width=7,
                   bg=T['input'], fg=T['fg'], font=('Segoe UI', 10)).pack(side=tk.LEFT)
        tk.Label(liq_row, text="crore per day (average traded value, last 20 days)", bg=T['bg'], fg=T['fg'],
                 font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=5)
        self.btn(liq_row, "Save", T['success'], self.save_liquidity_setting).pack(side=tk.LEFT, padx=10)
        tk.Label(liq_frame, text="Thinly traded stocks can gap past a stop-loss and orders may not fill, so their "
                                 "targets are shown with a warning and they can be hidden in Scan Results.",
                 bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 8)).pack(anchor=tk.W, padx=15, pady=(0, 8))

        # ===== SCORING WEIGHTS =====
        weights_frame = tk.LabelFrame(content, text=" Scoring Weights (must total 100%) ", 
                                      bg=T['bg'], fg=T['accent'], font=('Segoe UI', 11, 'bold'))
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
                    font=('Segoe UI', 10), width=14, anchor=tk.W).grid(row=row_num, column=col_num, padx=5, pady=4, sticky='w')

            var = tk.IntVar(value=Scorer.WEIGHTS.get(key, default))   # saved weights, if any
            self.weight_vars[key] = var

            tk.Spinbox(weights_grid, from_=0, to=100, textvariable=var, width=5,
                      bg=T['input'], fg=T['fg'], font=('Segoe UI', 10)).grid(row=row_num, column=col_num+1, padx=5, pady=4)

        weight_btns = tk.Frame(weights_frame, bg=T['bg'])
        weight_btns.pack(fill=tk.X, padx=10, pady=10)
        self.btn(weight_btns, "Apply Weights", T['success'], self.apply_weights).pack(side=tk.LEFT, padx=(0, 5))
        self.btn(weight_btns, "Reset Defaults", T['bg3'], self.reset_weights).pack(side=tk.LEFT, padx=5)
        tk.Label(weight_btns, text="Tip: the Backtest tab can suggest weights based on your stocks' history",
                 bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=10)
        
        # ===== MODULE STATUS =====
        status_frame = tk.LabelFrame(content, text=" Module Status ", 
                                    bg=T['bg'], fg=T['accent'], font=('Segoe UI', 11, 'bold'))
        status_frame.pack(fill=tk.X, padx=20, pady=10)
        
        modules = [
            ("Pattern Recognition", PATTERN_OK),
            ("AI/ML Engine", AI_OK),
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
                    font=('Segoe UI', 10)).pack(anchor=tk.W, padx=20, pady=3)
    
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
        self._set_weights(weights)
        messagebox.showinfo("Success", "Weights applied and saved!\n\nRe-scan (F5) to see updated scores.")

    def reset_weights(self):
        self._set_weights(dict(Scorer.DEFAULT_WEIGHTS))
        messagebox.showinfo("Reset", "Default weights restored.\n\nRe-scan (F5) to see updated scores.")

    def _set_weights(self, weights):
        """Use these weights for scoring from now on, and remember them across restarts."""
        Scorer.WEIGHTS.update(weights)
        if hasattr(self, 'weight_vars'):
            for k, v in weights.items():
                if k in self.weight_vars:
                    self.weight_vars[k].set(v)
        try:
            with open(WEIGHTS_FILE, 'w') as f:
                json.dump(weights, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save weights: {e}")

    @staticmethod
    def _load_app_settings():
        try:
            if APP_SETTINGS_FILE.exists():
                with open(APP_SETTINGS_FILE, 'r') as f:
                    data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"Could not load app settings: {e}")
        return {}

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
        try:
            if WEIGHTS_FILE.exists():
                with open(WEIGHTS_FILE, 'r') as f:
                    data = json.load(f)
                weights = {k: int(data[k]) for k in Scorer.DEFAULT_WEIGHTS}
                if sum(weights.values()) == 100 and min(weights.values()) >= 0:
                    Scorer.WEIGHTS.update(weights)
        except Exception as e:
            logger.error(f"Could not load weights: {e}")

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
        tk.Label(header, text="Help & Documentation", bg=T['bg2'], fg=T['gold'],
                font=('Segoe UI', 14, 'bold')).pack(side=tk.LEFT, padx=15)
        
        canvas = tk.Canvas(tab, bg=T['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=T['bg'])
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
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
            ("HOW TO USE", [
                ("1.", "Add stocks to watchlist"), ("2.", "Organize with Groups (Ctrl+G)"),
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
            ("LIQUIDITY", [
                ("Traded/day (Cr)", "Average daily traded value over the last 20 sessions, in Rs crore"),
                ("LOW", "Below the Settings threshold - stop-loss/targets less reliable"),
                ("Hide illiquid", "Scan Results checkbox to hide LOW stocks"),
            ]),
            ("SECTOR ROTATION", [
                ("LEADING", "Strong scores, outperforming - stay invested"),
                ("IMPROVING", "Rising scores - accumulate"),
                ("WEAKENING", "Declining scores - reduce exposure"),
                ("LAGGING", "Weak scores - avoid or short"),
            ]),
        ]
        
        for title, items in sections:
            sf = tk.LabelFrame(content, text=f" {title} ", bg=T['bg'], fg=T['gold'],
                              font=('Segoe UI', 12, 'bold'))
            sf.pack(fill=tk.X, padx=20, pady=10)
            for key, val in items:
                row = tk.Frame(sf, bg=T['card'], padx=10, pady=4)
                row.pack(fill=tk.X, padx=10, pady=2)
                tk.Label(row, text=key, bg=T['card'], fg=T['accent'],
                        font=('Segoe UI', 10, 'bold'), width=16, anchor=tk.W).pack(side=tk.LEFT)
                tk.Label(row, text=val, bg=T['card'], fg=T['fg'],
                        font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=10)
    

    def _setup_market_status(self):
        """Update market status indicator."""
        try:
            from datetime import datetime
            now = datetime.now()
            hour, minute = now.hour, now.minute
            weekday = now.weekday()
            is_open = weekday < 5 and ((hour == 9 and minute >= 15) or (10 <= hour < 15) or (hour == 15 and minute <= 30))
            if is_open:
                self.market_dot.delete('all')
                self.market_dot.create_oval(2, 2, 10, 10, fill='#10b981', outline='')
                self.market_status_lbl.configure(text="MARKET OPEN", fg='#10b981')
            else:
                self.market_dot.delete('all')
                self.market_dot.create_oval(2, 2, 10, 10, fill='#ef4444', outline='')
                self.market_status_lbl.configure(text="MARKET CLOSED", fg='#ef4444')
        except:
            pass
        self.root.after(60000, self._setup_market_status)

    def _create_group(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("New Group", "Enter group name:", parent=self.root)
        if name and name.strip():
            name = name.strip()
            if name not in self.watchlist_groups:
                self.watchlist_groups[name] = []
                self.group_cb.configure(values=list(self.watchlist_groups.keys()))
                self.group_var.set(name)
                self._switch_group()
                self.save_watchlist_groups()

    def _add_to_group(self):
        sel = self.wl_list.curselection()
        if not sel:
            messagebox.showinfo("Info", "Select a stock first!")
            return
        stock = self._wl_symbol(self.wl_list.get(sel[0]))
        group = self.group_var.get()
        if group == 'All Stocks':
            messagebox.showinfo("Info", "Select a specific group first")
            return
        if stock not in self.watchlist_groups[group]:
            self.watchlist_groups[group].append(stock)
            self.save_watchlist_groups()
            messagebox.showinfo("Added", f"{stock} added to '{group}'")

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
            fp = BASE_DIR / "watchlist_groups.json"
            with open(fp, 'w') as f:
                json.dump(self.watchlist_groups, f, indent=2)
        except: pass

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
            if isinstance(w, tk.Toplevel):
                w.destroy()
                return
        if hasattr(self, 'search_var'):
            self.search_var.set("")

    def _select_all_results(self):
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children)

    def add_stock(self):
        s = self.entry.get().strip().upper()
        if not s: return
        s = re.sub(r'[^A-Z0-9&-]', '', s)
        if not s or len(s) < 2: return
        if s in self.watchlist:
            messagebox.showinfo("Info", f"{s} already in list!")
            return
        self.watchlist.append(s)
        self.entry.delete(0, tk.END)
        self.refresh_watchlist()
        self.save_watchlist()
    
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
            self.wl_list.insert(tk.END, f"{s}{tag}")
        self.wl_count.configure(text=f"Stocks: {len(stocks)}")
        if hasattr(self, 'group_count_lbl'):
            self.group_count_lbl.configure(text=f"Group: {group} | {len(stocks)} stocks")
    
    def save_watchlist(self):
        try:
            with open(WATCHLIST_FILE, 'w') as f:
                json.dump(self.watchlist, f)
        except: pass
    
    def load_watchlist(self):
        try:
            if WATCHLIST_FILE.exists():
                with open(WATCHLIST_FILE, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.watchlist = data
        except: self.watchlist = []
    
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
                        if s and len(s) >= 2 and s.replace('-', '').isalpha():
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
                                if s and len(s) >= 2 and s.isalpha() and len(s) <= 15:
                                    imported.append(s)
            elif ext == '.json':
                with open(fp, 'r') as f:
                    data = json.load(f)
                    imported = data.get('watchlist', data) if isinstance(data, dict) else data
            elif ext == '.csv':
                with open(fp, 'r') as f:
                    imported = [row[0] for row in csv.reader(f) if row]
            else:
                with open(fp, 'r') as f:
                    imported = [l.strip() for l in f if l.strip()]
            
            added = 0
            for s in set(str(x).strip().upper() for x in imported if str(x).strip()):
                if s not in self.watchlist and len(s) >= 2:
                    self.watchlist.append(s)
                    added += 1
            
            self.refresh_watchlist()
            self.save_watchlist()
            messagebox.showinfo("Imported", f"Added {added} stocks from {os.path.basename(fp)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
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
                           'Traded/day (Rs Cr)', 'Liquidity']
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
            logo_path = LOGO_PATH
            
            def add_header(canvas_obj, doc):
                canvas_obj.saveState()
                if logo_path.exists():
                    try:
                        canvas_obj.drawImage(str(logo_path), 30, A4[1] - 80, width=50, height=50, preserveAspectRatio=True, mask='auto')
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
                    r['symbol'], f"{r['price']:.2f}", f"{r['change']:+.2f}%",
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
        
        header = tk.Frame(log_win, bg=THEME['bg2'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=f"Application Log: {log_path}", bg=THEME['bg2'], fg=THEME['gold'],
                font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT, padx=15)
        
        text_frame = tk.Frame(log_win, bg=THEME['bg'])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        log_text = tk.Text(text_frame, bg=THEME['input'], fg=THEME['fg'], font=('Consolas', 10),
                          relief=tk.FLAT, yscrollcommand=scrollbar.set)
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
                bg=T['bg'], fg=T['gold'], font=('Segoe UI', 20, 'bold')).pack(pady=20)
        
        summary = patterns.get('summary', {})
        total = summary.get('total_patterns', 0)
        bullish = summary.get('bullish_count', 0)
        bearish = summary.get('bearish_count', 0)
        overall = summary.get('overall_signal', 'N/A')
        
        stats_frame = tk.Frame(self.pt_frame, bg=T['card'])
        stats_frame.pack(fill=tk.X, padx=80, pady=10)
        
        for label, value, color in [("Total", str(total), T['accent']),
                                     ("Bullish", str(bullish), T['success']),
                                     ("Bearish", str(bearish), T['danger']),
                                     ("Overall", overall, T['success'] if overall == 'BULLISH' else T['danger'] if overall == 'BEARISH' else T['warning'])]:
            box = tk.Frame(stats_frame, bg=T['bg3'], padx=15, pady=8)
            box.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
            tk.Label(box, text=label, bg=T['bg3'], fg=T['fg3'], font=('Segoe UI', 9)).pack()
            tk.Label(box, text=value, bg=T['bg3'], fg=color, font=('Segoe UI', 18, 'bold')).pack()

        ignored = summary.get('ignored_conflicts') or []
        if ignored:
            tk.Label(self.pt_frame, text=f"Ignored conflicting pattern(s): {', '.join(ignored)} - a stronger or more recent "
                                         f"pattern points the other way",
                     bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 9, 'italic')).pack(pady=(0, 5))

        # Chart Patterns
        chart_patterns = patterns.get('chart', [])
        if chart_patterns:
            section = tk.LabelFrame(self.pt_frame, text=" CHART PATTERNS ", bg=T['bg'], fg=T['accent'], font=('Segoe UI', 12, 'bold'))
            section.pack(fill=tk.X, padx=80, pady=10)
            for pattern in chart_patterns:
                p_frame = tk.Frame(section, bg=T['card'], padx=10, pady=8)
                p_frame.pack(fill=tk.X, padx=10, pady=4)
                signal_color = T['success'] if pattern.get('signal') == 'BULLISH' else T['danger'] if pattern.get('signal') == 'BEARISH' else T['warning']
                tk.Label(p_frame, text=pattern.get('name', ''), bg=T['card'], fg=T['fg'], font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT)
                tk.Label(p_frame, text=f" {pattern.get('signal', '')} ", bg=signal_color, fg='white', font=('Segoe UI', 9, 'bold'), padx=8, pady=2).pack(side=tk.LEFT, padx=10)
                if pattern.get('description'):
                    tk.Label(p_frame, text=pattern['description'], bg=T['card'], fg=T['fg3'], font=('Segoe UI', 10), wraplength=600).pack(anchor=tk.W)
        else:
            tk.Label(self.pt_frame, text="No chart patterns detected", bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 11)).pack(pady=10)
        
        # Candlestick Patterns
        candle_patterns = patterns.get('candlestick', [])
        if candle_patterns:
            section = tk.LabelFrame(self.pt_frame, text=" CANDLESTICK PATTERNS ", bg=T['bg'], fg=T['accent'], font=('Segoe UI', 12, 'bold'))
            section.pack(fill=tk.X, padx=80, pady=10)
            for pattern in candle_patterns:
                p_frame = tk.Frame(section, bg=T['card'], padx=10, pady=8)
                p_frame.pack(fill=tk.X, padx=10, pady=4)
                signal_color = T['success'] if pattern.get('signal') == 'BULLISH' else T['danger'] if pattern.get('signal') == 'BEARISH' else T['warning']
                tk.Label(p_frame, text=pattern.get('name', ''), bg=T['card'], fg=T['fg'], font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT)
                tk.Label(p_frame, text=f" {pattern.get('signal', '')} ", bg=signal_color, fg='white', font=('Segoe UI', 9, 'bold'), padx=8, pady=2).pack(side=tk.LEFT, padx=10)
        else:
            tk.Label(self.pt_frame, text="No candlestick patterns detected", bg=T['bg'], fg=T['fg3'], font=('Segoe UI', 11)).pack(pady=10)
        
        self.nb.select(4)
    
    def sort_tree(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        
        def num(text):   # leading number of a cell, e.g. '+1.25%' -> 1.25, '0.42 LOW' -> 0.42
            m = re.match(r'\s*([+-]?\d+(?:\.\d+)?)', text.replace(',', ''))
            return float(m.group(1)) if m else None
        
        if all(num(t[0]) is not None for t in items):
            items.sort(key=lambda t: num(t[0]))
        else:
            items.sort(key=lambda t: t[0])
        if not hasattr(self, '_sort_col') or self._sort_col != col:
            self._sort_asc = True
            self._sort_col = col
        elif self._sort_col == col:
            self._sort_asc = not self._sort_asc
        if not self._sort_asc:
            items.reverse()
        for index, (val, k) in enumerate(items):
            self.tree.move(k, '', index)
    
    def start_scan(self):
        if not self.watchlist:
            messagebox.showwarning("Warning", "Add stocks first!")
            return
        if self.scanning: return
        self.scanning = True
        self.scan_btn.configure(state=tk.DISABLED, text="SCANNING...")
        self.results = []
        self.tree.delete(*self.tree.get_children())
        threading.Thread(target=self._scan, daemon=True).start()
    
    def _scan(self):
        watchlist = list(self.watchlist)
        total = len(watchlist)
        failed = []
        t0 = time.time()
        
        # 1. Download every stock's prices in one batch (disk-cached; re-scans only fetch recent days)
        self.gui.schedule(self._status, f"Downloading prices for {total} stocks...", 2)
        try:
            frames = self.analyzer.fetch_many(
                watchlist, progress=lambda msg: self.gui.schedule(self._status, msg, 5))
        except Exception as e:
            logger.error(f"Batch download failed: {e}")
            frames = {}
        
        # 2. Analyse each stock (CPU only - no network)
        for i, sym in enumerate(watchlist):
            self.gui.schedule(self._status, f"Analysing {sym} ({i+1}/{total})...", 10 + (i / total) * 90)
            df = frames.get(sym)
            if df is None or df.empty or len(df) < 20:
                self.gui.schedule(self._add_error, sym, "No data / delisted")
                failed.append(sym)
                continue
            try:
                data = self.analyzer.analyze(df)
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
                    'patterns': data.get('patterns', {}), 'ai': data.get('ai', {}),
                    'high52': high52, 'low52': low52
                }
                self.results.append(result)
                self.gui.schedule(self._add_tree, result)
            except Exception as e:
                logger.error(f"Scan {sym}: {e}")
                self.gui.schedule(self._add_error, sym, str(e)[:30])
                failed.append(sym)
        
        logger.info(f"Scan: {total - len(failed)}/{total} stocks in {time.time() - t0:.1f}s")
        self.results.sort(key=lambda x: x['symbol'])
        self.gui.schedule(self._scan_done, failed)
    
    def _status(self, msg, pct):
        self.status_lbl.configure(text=msg)
        self.progress['value'] = pct
    
    def _add_tree(self, r):
        tags = {'STRONG BUY': 'sb', 'BUY': 'buy', 'HOLD': 'hold', 'SELL': 'sell', 'STRONG SELL': 'ss'}
        tag = tags.get(r['rec'], '')
        
        # Get additional data
        data = r.get('data', {})
        high52 = r.get('high52', 0)
        low52 = r.get('low52', 0)
        atr = safe_float(data.get('atr', 0))
        liq = self._liquidity_text(r)
        
        self.tree.insert('', tk.END, values=(
            r['symbol'], f"{r['price']:.2f}", f"{r['change']:+.2f}%",
            f"{r['rsi']:.1f}", r.get('st_sig', ''), r.get('vwap_sig', ''),
            f"{r['score']:.1f}", r['rec'],
            f"{high52:.2f}", f"{low52:.2f}", f"{atr:.2f}", liq
        ), tags=(tag,))
        
        self.tree.tag_configure('sb', background='#059669', foreground='white')
        self.tree.tag_configure('buy', background='#10b981', foreground='white')
        self.tree.tag_configure('hold', background='#d97706', foreground='white')
        self.tree.tag_configure('sell', background='#ef4444', foreground='white')
        self.tree.tag_configure('ss', background='#dc2626', foreground='white')
    
    def _scan_done(self, failed=None):
        self.scanning = False
        self.scan_btn.configure(state=tk.NORMAL, text="SCAN ALL STOCKS")
        self.progress['value'] = 100
        self.status_lbl.configure(text="Complete!")
        
        self.results.sort(key=lambda x: x['symbol'])
        self.tree.delete(*self.tree.get_children())
        for r in self.results:
            self._add_tree(r)
        
        self._all_results = self.results.copy()
        
        self.nb.select(1)
        self.update_dash()
        self.last_scan_lbl.configure(text=f"Last Scan: {datetime.now().strftime('%H:%M:%S')}")
        
        msg = f"Scanned {len(self.results)} stocks!"
        if failed:
            msg += f"\n{len(failed)} failed: {', '.join(failed[:5])}"
        messagebox.showinfo("Done", msg)
    
    def _add_error(self, symbol, error):
        """Add error entry to tree."""
        self.tree.insert('', tk.END, values=(
            symbol, 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', f'Error: {error}',
            'N/A', 'N/A', 'N/A', 'N/A'
        ), tags=('error',))
        self.tree.tag_configure('error', background='#636e72', foreground='white')
    
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
    
    def update_dash(self):
        if not self.results: return
        n = len(self.results)
        self.dash_cards['total'].configure(text=str(n))
        self.dash_cards['sb'].configure(text=str(sum(1 for r in self.results if r['rec'] == 'STRONG BUY')))
        self.dash_cards['buy'].configure(text=str(sum(1 for r in self.results if r['rec'] == 'BUY')))
        self.dash_cards['hold'].configure(text=str(sum(1 for r in self.results if r['rec'] == 'HOLD')))
        self.dash_cards['sell'].configure(text=str(sum(1 for r in self.results if r['rec'] == 'SELL')))
        self.dash_cards['ss'].configure(text=str(sum(1 for r in self.results if r['rec'] == 'STRONG SELL')))
        self.dash_cards['avg'].configure(text=f"{sum(r['score'] for r in self.results)/n:.1f}")
    
    def show_details(self, event):
        sel = self.tree.selection()
        if not sel: return
        sym = str(self.tree.item(sel[0])['values'][0])  # Treeview turns numeric symbols (BSE codes) into int
        r = next((x for x in self.results if x['symbol'] == sym), None)
        if not r: return
        self.update_breakdown(r)
        self.update_targets(r)
        self.update_patterns(r)
        self.nb.select(2)
    
    def update_breakdown(self, r):
        T = THEME
        for w in self.bd_frame.winfo_children():
            w.destroy()
        
        score = r['score']
        color = '#059669' if score >= 75 else '#10b981' if score >= 60 else '#d97706' if score >= 45 else '#ef4444'
        
        tk.Label(self.bd_frame, text=f"Score Breakdown: {r['symbol']}",
                bg=T['bg'], fg=T['gold'], font=('Segoe UI', 20, 'bold')).pack(pady=20)
        
        canvas = tk.Canvas(self.bd_frame, width=150, height=150, bg=T['bg'], highlightthickness=0)
        canvas.pack(pady=10)
        canvas.create_oval(10, 10, 140, 140, fill=T['card'], outline=color, width=4)
        canvas.create_text(75, 60, text=f"{score}", fill=color, font=('Segoe UI', 36, 'bold'))
        canvas.create_text(75, 100, text="/100", fill=T['fg3'], font=('Segoe UI', 12))
        
        tk.Label(self.bd_frame, text=r['rec'], bg=T['bg'], fg=color, font=('Segoe UI', 16, 'bold')).pack(pady=5)
        tk.Label(self.bd_frame, text=f"Price: {r['price']:.2f} | Change: {r['change']:+.2f}%",
                bg=T['bg'], fg=T['fg'], font=('Segoe UI', 12)).pack(pady=5)
        
        names = {'rsi': 'RSI', 'macd': 'MACD', 'ma': 'Moving Avg', 'boll': 'Bollinger',
                'stoch': 'Stochastic', 'adx': 'ADX', 'vol': 'Volume', 'mom': 'Momentum',
                'st': 'SuperTrend', 'vwap': 'VWAP'}
        
        for key, val in r['breakdown'].items():
            row = tk.Frame(self.bd_frame, bg=T['bg'])
            row.pack(fill=tk.X, padx=100, pady=4)
            
            tk.Label(row, text=f"{names.get(key, key)}:", bg=T['bg'], fg=T['fg'],
                    font=('Segoe UI', 11), width=14, anchor=tk.W).pack(side=tk.LEFT)
            
            bar = tk.Canvas(row, height=24, bg=T['bg3'], highlightthickness=0)
            bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
            
            c = '#059669' if val >= 70 else '#10b981' if val >= 50 else '#d97706' if val >= 30 else '#ef4444'
            bar.create_rectangle(0, 0, int(val * 2.5), 24, fill=c, outline='')
            bar.create_text(int(val * 2.5) // 2, 12, text=f"{val}", fill='white', font=('Segoe UI', 10, 'bold'))
            
            lbl = "Strong" if val >= 70 else "Good" if val >= 50 else "Weak" if val >= 30 else "Bearish"
            tk.Label(row, text=lbl, bg=T['bg'], fg=c, font=('Segoe UI', 9), width=8).pack(side=tk.LEFT)
    
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
                bg=T['bg'], fg=T['gold'], font=('Segoe UI', 20, 'bold')).pack(pady=20)
        
        tk.Label(self.tg_frame, text=f"{price:,.2f}", bg=T['card'], fg='white',
                font=('Segoe UI', 28, 'bold')).pack(pady=10, padx=100, fill=tk.X)
        
        rec_c = '#059669' if rec in ['STRONG BUY', 'BUY'] else '#ef4444' if rec in ['SELL', 'STRONG SELL'] else '#d97706'
        tk.Label(self.tg_frame, text=f"{rec} | {t.get('pos', '')}", bg=T['bg'], fg=rec_c,
                font=('Segoe UI', 14, 'bold')).pack(pady=10)

        if self._is_illiquid(r):
            liq = r.get('data', {}).get('liquidity_cr', 0)
            tk.Label(self.tg_frame, text=f"LOW LIQUIDITY: only about Rs {liq:.2f} crore traded per day "
                                         f"(threshold Rs {self.min_liquidity_cr:g} Cr).\n"
                                         "Price can gap past the stop-loss and orders may not fill - treat these levels with caution.",
                     bg='#78350f', fg='#fde68a', font=('Segoe UI', 10, 'bold'), padx=12, pady=8,
                     justify=tk.LEFT).pack(fill=tk.X, padx=100, pady=(0, 10))
        
        levels = [
            ("STOP LOSS", t.get('sl', 0), '#ef4444', 'Exit if price falls below'),
            ("TARGET 1 (Conservative)", t.get('t1', 0), '#10b981', 'Book partial profits'),
            ("TARGET 2 (Moderate)", t.get('t2', 0), '#059669', 'Main target - book 50%'),
            ("TARGET 3 (Aggressive)", t.get('t3', 0), '#3b82f6', 'Trail stop loss'),
        ]
        
        for label, val, color, desc in levels:
            frame = tk.Frame(self.tg_frame, bg=T['card'], highlightbackground=color, highlightthickness=2)
            frame.pack(fill=tk.X, padx=100, pady=6)
            tk.Label(frame, text=label, bg=T['card'], fg=color, font=('Segoe UI', 11, 'bold')).pack(anchor=tk.W, padx=15, pady=(10, 0))
            tk.Label(frame, text=f"{val:,.2f}" if val else "N/A", bg=T['card'], fg=color, font=('Segoe UI', 22, 'bold')).pack(padx=15, pady=5)
            tk.Label(frame, text=desc, bg=T['card'], fg=T['fg3'], font=('Segoe UI', 9)).pack(anchor=tk.W, padx=15, pady=(0, 10))
        
        # Risk-Reward
        rr_frame = tk.Frame(self.tg_frame, bg=T['card'], highlightbackground=T['gold'], highlightthickness=2)
        rr_frame.pack(fill=tk.X, padx=100, pady=15)
        
        tk.Label(rr_frame, text="RISK-REWARD ANALYSIS", bg=T['card'], fg=T['gold'], font=('Segoe UI', 14, 'bold')).pack(pady=(15, 10))
        
        risk_amt = t.get('risk', 0) or 0
        reward_amt = t.get('reward', 0) or 0
        rr = t.get('rr', 0) or 0
        
        boxes = tk.Frame(rr_frame, bg=T['card'])
        boxes.pack(fill=tk.X, padx=20, pady=10)
        
        # Risk
        rb = tk.Frame(boxes, bg='#7f1d1d', highlightbackground='#ef4444', highlightthickness=1)
        rb.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
        tk.Label(rb, text="RISK", bg='#7f1d1d', fg='#fca5a5', font=('Segoe UI', 10, 'bold')).pack(pady=(10, 2))
        tk.Label(rb, text=f"{risk_amt:,.2f}", bg='#7f1d1d', fg='white', font=('Segoe UI', 22, 'bold')).pack(pady=2)
        tk.Label(rb, text=f"{(risk_amt/price*100):.1f}%" if price > 0 else "", bg='#7f1d1d', fg='#fca5a5', font=('Segoe UI', 10)).pack(pady=(0, 10))
        
        tk.Label(boxes, text="-->", bg=T['card'], fg='white', font=('Segoe UI', 24, 'bold')).pack(side=tk.LEFT, padx=15)
        
        # Reward
        rwb = tk.Frame(boxes, bg='#064e3b', highlightbackground='#10b981', highlightthickness=1)
        rwb.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
        tk.Label(rwb, text="REWARD", bg='#064e3b', fg='#6ee7b7', font=('Segoe UI', 10, 'bold')).pack(pady=(10, 2))
        tk.Label(rwb, text=f"{reward_amt:,.2f}", bg='#064e3b', fg='white', font=('Segoe UI', 22, 'bold')).pack(pady=2)
        tk.Label(rwb, text=f"{(reward_amt/price*100):.1f}%" if price > 0 else "", bg='#064e3b', fg='#6ee7b7', font=('Segoe UI', 10)).pack(pady=(0, 10))
        
        # Ratio
        rr_c = '#059669' if rr >= 2 else '#10b981' if rr >= 1.5 else '#d97706' if rr >= 1 else '#ef4444'
        quality = "EXCELLENT" if rr >= 2 else "GOOD" if rr >= 1.5 else "ACCEPTABLE" if rr >= 1 else "POOR"
        
        tk.Label(rr_frame, text="Risk : Reward", bg=T['card'], fg=T['fg3'], font=('Segoe UI', 11)).pack(pady=(15, 5))
        tk.Label(rr_frame, text=f"1 : {rr:.2f}" if rr > 0 else "N/A", bg=T['card'], fg=rr_c, font=('Segoe UI', 36, 'bold')).pack(pady=5)
        tk.Label(rr_frame, text=f"Quality: {quality}", bg=T['card'], fg=rr_c, font=('Segoe UI', 14, 'bold')).pack(pady=(5, 15))
        
        # Advice
        advice_f = tk.Frame(self.tg_frame, bg=T['card'], highlightbackground=T['warning'], highlightthickness=1)
        advice_f.pack(fill=tk.X, padx=100, pady=15)
        
        tk.Label(advice_f, text="TRADING ADVICE", bg=T['card'], fg=T['warning'], font=('Segoe UI', 12, 'bold')).pack(pady=(10, 5))
        
        if rec in ['STRONG BUY', 'BUY']:
            advice = f"Enter at: {price:,.2f}\nStop Loss: {t.get('sl', 0):,.2f}\nTarget: {t.get('t1', 0):,.2f}\nRisk: {(risk_amt/price*100):.1f}% per trade"
        elif rec in ['SELL', 'STRONG SELL']:
            advice = f"Exit at: {price:,.2f}\nStop Loss: {t.get('sl', 0):,.2f}\nTarget: {t.get('t1', 0):,.2f}"
        else:
            advice = f"Support: {t.get('sl', 0):,.2f}\nResistance: {t.get('t1', 0):,.2f}\nWait for breakout"
        
        tk.Label(advice_f, text=advice, bg=T['card'], fg=T['fg'], font=('Segoe UI', 11), justify=tk.LEFT).pack(padx=15, pady=15)
        
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
        
        # Top picks section
        top_picks = [r for r in sorted_results if r['rec'] in ['STRONG BUY', 'BUY']][:5]
        if top_picks:
            html += '<div class="section"><h2>Top Picks</h2><table>'
            html += '<tr><th>Symbol</th><th>Price</th><th>Change%</th><th>RSI</th><th>Score</th><th>Signal</th><th>Stop Loss</th><th>Target 1</th><th>R:R</th></tr>'
            for r in top_picks:
                t = r.get('targets', {})
                html += f'<tr class="top-pick"><td><b>{r["symbol"]}</b></td><td>{r["price"]:.2f}</td><td>{r["change"]:+.2f}%</td><td>{r["rsi"]:.0f}</td><td><b>{r["score"]:.0f}</b></td><td><span class="{r["rec"].lower().replace(" ", "-")}">{r["rec"]}</span></td><td>{t.get("sl", "N/A")}</td><td>{t.get("t1", "N/A")}</td><td>1:{t.get("rr", 0)}</td></tr>'
            html += '</table></div>'
        
        # All results table
        html += '<div class="section"><h2>All Watchlist Results</h2><table>'
        html += '<tr><th>#</th><th>Symbol</th><th>Price</th><th>Change%</th><th>RSI</th><th>SuperTrend</th><th>Score</th><th>Signal</th><th>Stop Loss</th><th>Target 1</th><th>Traded/day (Cr)</th></tr>'
        
        for i, r in enumerate(sorted_results, 1):
            t = r.get('targets', {})
            rec_class = r['rec'].lower().replace(' ', '-')
            row_class = 'top-pick' if r['rec'] in ['STRONG BUY', 'BUY'] else 'avoid' if r['rec'] in ['SELL', 'STRONG SELL'] else ''
            html += f'<tr class="{row_class}"><td>{i}</td><td><b>{r["symbol"]}</b></td><td>{r["price"]:.2f}</td><td>{r["change"]:+.2f}%</td><td>{r["rsi"]:.0f}</td><td>{r.get("st_sig", "")}</td><td>{r["score"]:.0f}</td><td><span class="{rec_class}">{r["rec"]}</span></td><td>{t.get("sl", "N/A")}</td><td>{t.get("t1", "N/A")}</td><td>{self._liquidity_text(r)}</td></tr>'
        
        html += '</table>'
        html += (f'<p style="font-size:11px;color:#666">LOW = average traded value below Rs {self.min_liquidity_cr:g} crore/day: '
                 'stop-loss and targets are less reliable for these stocks.</p></div>')
        
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
        
        logo_path = LOGO_PATH
        
        def add_header(canvas_obj, doc):
            canvas_obj.saveState()
            if logo_path.exists():
                try:
                    canvas_obj.drawImage(str(logo_path), 25, A4[1] - 75, 
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
                str(i), r['symbol'], f"{r['price']:.2f}", f"{r['change']:+.1f}%",
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
    check("backtest", lambda: f"{backtest.build_samples({'RELIANCE': data['RELIANCE']}, Scorer)[0].shape[0]} stock-days")

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
    check("chart", chart)

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

    lines.append("RESULT: " + ("ALL PASSED" if not failed else f"{len(failed)} FAILED: {', '.join(failed)}"))
    (DATA_DIR / "self_test_result.txt").write_text("\n".join(lines), encoding='utf-8')
    return 0 if not failed else 1


def main():
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    if '--scheduled-report' in sys.argv:
        # Started by Windows Task Scheduler (packaged .exe): email the report without opening the window
        import scheduled_report
        sys.exit(scheduled_report.main())
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
