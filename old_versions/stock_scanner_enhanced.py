#!/usr/bin/env python3
"""
DR. SHAH'S Analysis - Stock Technical Scanner & Recommender
============================================================
Version 3.0 - Modern Dashboard, Themes, Tooltips, Categories
"""

import sys
import os
import json
import csv
import threading
import time
import re
import queue
import logging
from datetime import datetime, timedelta

# Check Python version
if sys.version_info < (3, 7):
    print("ERROR: Python 3.7 or higher is required!")
    input("Press Enter to exit...")
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
    print(f"Missing required package: {e}")
    print("Run: pip install yfinance pandas numpy ta openpyxl")
    input("Press Enter to exit...")
    sys.exit(1)

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Logging
logging.basicConfig(filename='stock_scanner.log', level=logging.INFO, 
                   format='%(asctime)s - %(message)s', filemode='a')
logger = logging.getLogger(__name__)


# ============================================================
# THEME CONFIGURATION
# ============================================================

THEMES = {
    'dark': {
        'bg_primary': '#0d1117',
        'bg_secondary': '#161b22',
        'bg_card': '#21262d',
        'bg_input': '#0d1117',
        'fg_primary': '#f0f6fc',
        'fg_secondary': '#8b949e',
        'fg_accent': '#58a6ff',
        'fg_success': '#3fb950',
        'fg_warning': '#d29922',
        'fg_danger': '#f85149',
        'fg_info': '#58a6ff',
        'border': '#30363d',
        'hover': '#30363d',
        'selected': '#1f6feb',
        'button_primary': '#238636',
        'button_secondary': '#21262d',
        'button_danger': '#da3633',
        'button_info': '#1f6feb',
        'shadow': '#000000',
    },
    'light': {
        'bg_primary': '#ffffff',
        'bg_secondary': '#f6f8fa',
        'bg_card': '#ffffff',
        'bg_input': '#ffffff',
        'fg_primary': '#24292f',
        'fg_secondary': '#57606a',
        'fg_accent': '#0969da',
        'fg_success': '#1a7f37',
        'fg_warning': '#9a6700',
        'fg_danger': '#cf222e',
        'fg_info': '#0969da',
        'border': '#d0d7de',
        'hover': '#f3f4f6',
        'selected': '#ddf4ff',
        'button_primary': '#2da44e',
        'button_secondary': '#f6f8fa',
        'button_danger': '#cf222e',
        'button_info': '#0969da',
        'shadow': '#8c959f',
    }
}

SECTOR_MAP = {
    'Banking': ['HDFCBANK', 'ICICIBANK', 'SBIN', 'KOTAKBANK', 'AXISBANK', 'INDUSINDBK', 'FEDERALBNK', 'BANDHANBNK', 'IDFCFIRSTB'],
    'IT': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTIM', 'MPHASIS', 'COFORGE', 'PERSISTENT', 'LTTS'],
    'Auto': ['MARUTI', 'TATAMOTORS', 'BAJAJ-AUTO', 'HEROMOTOCO', 'EICHERMOT', 'M&M', 'TVSMOTOR', 'BAJFINANCE'],
    'Pharma': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'LUPIN', 'BIOCON', 'TORNTPHARM', 'ALKEM'],
    'FMCG': ['HINDUNILVR', 'ITC', 'NESTLEIND', 'BRITANNIA', 'DABUR', 'MARICO', 'GODREJCP', 'TATACONSUM'],
    'Energy': ['RELIANCE', 'ONGC', 'BPCL', 'POWERGRID', 'NTPC', 'GAIL', 'IOC', 'HINDPETRO'],
    'Metals': ['TATASTEEL', 'JSWSTEEL', 'HINDALCO', 'VEDL', 'NATIONALUM', 'JINDALSTEL', 'SAIL', 'NMDC'],
    'Infrastructure': ['LT', 'ADANIENT', 'ADANIPORTS', 'ADANIGREEN', 'ADANITRANS', 'GMRINFRA', 'IRCON', 'RVNL'],
}


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        val = float(value)
        if pd.isna(val) or np.isnan(val) or np.isinf(val):
            return default
        return val
    except:
        return default


def is_valid_number(value):
    try:
        if value is None:
            return False
        val = float(value)
        return not (pd.isna(val) or np.isnan(val) or np.isinf(val))
    except:
        return False


class DataCache:
    def __init__(self, cache_duration_hours=4):
        self.cache = {}
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self._lock = threading.Lock()
    
    def get(self, symbol):
        with self._lock:
            if symbol in self.cache:
                data, timestamp = self.cache[symbol]
                if datetime.now() - timestamp < self.cache_duration:
                    return data
                else:
                    del self.cache[symbol]
        return None
    
    def set(self, symbol, data):
        with self._lock:
            self.cache[symbol] = (data, datetime.now())
    
    def clear(self):
        with self._lock:
            self.cache.clear()


class ThreadSafeGUI:
    def __init__(self, root):
        self.root = root
        self.update_queue = queue.Queue()
        self._process_queue()
    
    def _process_queue(self):
        try:
            while True:
                func, args, kwargs = self.update_queue.get_nowait()
                func(*args, **kwargs)
        except queue.Empty:
            pass
        self.root.after(50, self._process_queue)
    
    def schedule(self, func, *args, **kwargs):
        self.update_queue.put((func, args, kwargs))


class TechnicalAnalyzer:
    def __init__(self):
        self.cache = DataCache(cache_duration_hours=4)
    
    def fetch_stock_data(self, symbol, period="1y"):
        cache_key = f"{symbol}_{period}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            df = ticker.history(period=period)
            if df is None or df.empty:
                ticker = yf.Ticker(f"{symbol}.BO")
                df = ticker.history(period=period)
            if df is None:
                return pd.DataFrame()
            if not df.empty:
                self.cache.set(cache_key, df)
            return df
        except Exception as e:
            logger.error(f"Fetch error {symbol}: {e}")
            raise
    
    def calculate_all_indicators(self, df):
        if df is None or df.empty:
            raise ValueError("Empty data")
        
        try:
            rsi_val = ta.momentum.RSIIndicator(df['Close'], window=14).rsi().iloc[-1]
            rsi = safe_float(rsi_val, 50.0)
        except:
            rsi = 50.0
        
        try:
            macd_ind = ta.trend.MACD(df['Close'])
            macd = {
                'macd': safe_float(macd_ind.macd().iloc[-1]),
                'signal': safe_float(macd_ind.macd_signal().iloc[-1]),
                'histogram': safe_float(macd_ind.macd_diff().iloc[-1])
            }
        except:
            macd = {'macd': 0, 'signal': 0, 'histogram': 0}
        
        try:
            price = safe_float(df['Close'].iloc[-1])
            ma = {
                'sma_20': safe_float(ta.trend.SMAIndicator(df['Close'], 20).sma_indicator().iloc[-1], price),
                'sma_50': safe_float(ta.trend.SMAIndicator(df['Close'], 50).sma_indicator().iloc[-1], price) if len(df) >= 50 else price,
                'sma_200': safe_float(ta.trend.SMAIndicator(df['Close'], 200).sma_indicator().iloc[-1], price) if len(df) >= 200 else price,
                'ema_12': safe_float(ta.trend.EMAIndicator(df['Close'], 12).ema_indicator().iloc[-1], price),
                'ema_26': safe_float(ta.trend.EMAIndicator(df['Close'], 26).ema_indicator().iloc[-1], price)
            }
        except:
            price = safe_float(df['Close'].iloc[-1])
            ma = {'sma_20': price, 'sma_50': price, 'sma_200': price, 'ema_12': price, 'ema_26': price}
        
        try:
            bb = ta.volatility.BollingerBands(df['Close'])
            bollinger = {
                'upper': safe_float(bb.bollinger_hband().iloc[-1]),
                'middle': safe_float(bb.bollinger_mavg().iloc[-1]),
                'lower': safe_float(bb.bollinger_lband().iloc[-1])
            }
        except:
            price = safe_float(df['Close'].iloc[-1])
            bollinger = {'upper': price * 1.02, 'middle': price, 'lower': price * 0.98}
        
        try:
            stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
            stochastic = {'k': safe_float(stoch.stoch().iloc[-1], 50), 'd': safe_float(stoch.stoch_signal().iloc[-1], 50)}
        except:
            stochastic = {'k': 50, 'd': 50}
        
        try:
            adx = safe_float(ta.trend.ADXIndicator(df['High'], df['Low'], df['Close']).adx().iloc[-1], 25)
        except:
            adx = 25.0
        
        try:
            obv = ta.volume.OnBalanceVolumeIndicator(df['Close'], df['Volume'])
            obv_series = obv.on_balance_volume()
            obv_current = safe_float(obv_series.iloc[-1])
            obv_prev = safe_float(obv_series.iloc[-5]) if len(obv_series) >= 5 else obv_current
            obv_trend = ((obv_current - obv_prev) / abs(obv_prev) * 100) if obv_prev != 0 else 0
            obv_data = {'current': obv_current, 'trend': safe_float(obv_trend)}
        except:
            obv_data = {'current': 0, 'trend': 0}
        
        try:
            williams_r = safe_float(ta.momentum.WilliamsRIndicator(df['High'], df['Low'], df['Close']).williams_r().iloc[-1], -50)
        except:
            williams_r = -50.0
        
        try:
            cci = safe_float(ta.trend.CCIIndicator(df['High'], df['Low'], df['Close']).cci().iloc[-1], 0)
        except:
            cci = 0.0
        
        try:
            atr = safe_float(ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], 14).average_true_range().iloc[-1])
        except:
            atr = safe_float(df['Close'].iloc[-1]) * 0.02
        
        # SuperTrend
        try:
            if atr == 0:
                atr = safe_float(df['Close'].iloc[-1]) * 0.02
            hl2 = (df['High'] + df['Low']) / 2
            st_val = hl2.iloc[-1]
            st_signal = 'BUY' if safe_float(df['Close'].iloc[-1]) > st_val else 'SELL'
            st_direction = 'BULLISH' if st_signal == 'BUY' else 'BEARISH'
            supertrend = {'value': safe_float(st_val), 'signal': st_signal, 'direction': st_direction}
        except:
            supertrend = {'value': safe_float(df['Close'].iloc[-1]), 'signal': 'HOLD', 'direction': 'NEUTRAL'}
        
        # VWAP
        try:
            typical_price = (df['High'] + df['Low'] + df['Close']) / 3
            vwap_val = safe_float((typical_price * df['Volume']).rolling(20).sum().iloc[-1] / df['Volume'].rolling(20).sum().iloc[-1])
            current_price = safe_float(df['Close'].iloc[-1])
            if vwap_val == 0:
                vwap_val = current_price
            if current_price > vwap_val * 1.02:
                vwap_signal = 'BULLISH'
            elif current_price < vwap_val * 0.98:
                vwap_signal = 'BEARISH'
            else:
                vwap_signal = 'NEUTRAL'
            vwap = {'value': vwap_val, 'signal': vwap_signal, 'deviation': ((current_price - vwap_val) / vwap_val * 100) if vwap_val > 0 else 0}
        except:
            vwap = {'value': safe_float(df['Close'].iloc[-1]), 'signal': 'NEUTRAL', 'deviation': 0}
        
        return {
            'rsi': rsi, 'macd': macd, 'moving_averages': ma, 'bollinger': bollinger,
            'stochastic': stochastic, 'adx': adx, 'obv': obv_data, 'williams_r': williams_r,
            'cci': cci, 'atr': atr, 'supertrend': supertrend, 'vwap': vwap,
            'current_price': safe_float(df['Close'].iloc[-1]),
            'prev_close': safe_float(df['Close'].iloc[-2]) if len(df) > 1 else safe_float(df['Close'].iloc[-1])
        }


class StockScorer:
    def __init__(self):
        self.weights = {'rsi': 12, 'macd': 12, 'moving_averages': 15, 'bollinger': 8,
                       'stochastic': 8, 'adx': 8, 'volume': 8, 'momentum': 8, 'supertrend': 11, 'vwap': 10}
    
    def calculate_total_score(self, indicators):
        scores = {
            'rsi': self._score_rsi(indicators['rsi']),
            'macd': self._score_macd(indicators['macd']),
            'moving_averages': self._score_ma(indicators['current_price'], indicators['moving_averages']),
            'bollinger': self._score_bb(indicators['current_price'], indicators['bollinger']),
            'stochastic': self._score_stoch(indicators['stochastic']),
            'adx': self._score_adx(indicators['adx']),
            'volume': self._score_vol(indicators['obv']),
            'momentum': self._score_mom(indicators['williams_r'], indicators['cci']),
            'supertrend': self._score_st(indicators.get('supertrend', {})),
            'vwap': self._score_vwap(indicators.get('vwap', {}))
        }
        total = sum(scores[k] * self.weights[k] / 100 for k in scores)
        rec = "STRONG BUY" if total >= 75 else "BUY" if total >= 60 else "HOLD" if total >= 45 else "SELL" if total >= 30 else "STRONG SELL"
        return {'total': round(total, 1), 'breakdown': scores, 'recommendation': rec}
    
    def _score_rsi(self, rsi):
        rsi = safe_float(rsi, 50)
        if rsi < 20: return 90
        elif rsi < 30: return 75
        elif rsi < 40: return 60
        elif rsi < 50: return 50
        elif rsi < 60: return 45
        elif rsi < 70: return 35
        elif rsi < 80: return 20
        else: return 10
    
    def _score_macd(self, m):
        h = safe_float(m['histogram'])
        score = 50 + (25 if h > 0 else -25) + (15 if safe_float(m['macd']) > safe_float(m['signal']) else -15)
        return max(0, min(100, score))
    
    def _score_ma(self, price, ma):
        score = 50
        for v in ma.values():
            v = safe_float(v)
            if v > 0:
                score += 10 if price > v else -10
        s50, s200 = safe_float(ma.get('sma_50')), safe_float(ma.get('sma_200'))
        if s50 > 0 and s200 > 0:
            score += 10 if s50 > s200 else -10
        return max(0, min(100, score))
    
    def _score_bb(self, price, bb):
        u, l = safe_float(bb['upper']), safe_float(bb['lower'])
        if u == 0 or l == 0 or u == l: return 50
        pos = (price - l) / (u - l)
        if pos < 0.1: return 80
        elif pos < 0.3: return 65
        elif pos < 0.5: return 50
        elif pos < 0.7: return 40
        elif pos < 0.9: return 30
        else: return 15
    
    def _score_stoch(self, s):
        k, d = safe_float(s['k'], 50), safe_float(s['d'], 50)
        score = 50 + (30 if k < 20 else 15 if k < 30 else -30 if k > 80 else -15 if k > 70 else 0)
        score += 10 if k > d else -10
        return max(0, min(100, score))
    
    def _score_adx(self, adx):
        adx = safe_float(adx, 25)
        return 80 if adx > 50 else 70 if adx > 40 else 60 if adx > 30 else 50 if adx > 20 else 30
    
    def _score_vol(self, obv):
        t = safe_float(obv.get('trend', 0))
        return 80 if t > 10 else 65 if t > 5 else 55 if t > 0 else 45 if t > -5 else 35 if t > -10 else 20
    
    def _score_mom(self, wr, cci):
        score = 50
        wr = safe_float(wr, -50)
        if wr < -80: score += 20
        elif wr > -20: score -= 20
        cci = safe_float(cci, 0)
        if cci < -100: score += 15
        elif cci > 100: score -= 15
        return max(0, min(100, score))
    
    def _score_st(self, st):
        if not st: return 50
        s, d = st.get('signal', 'HOLD'), st.get('direction', 'NEUTRAL')
        if s == 'BUY' and d == 'BULLISH': return 85
        elif s == 'BUY': return 70
        elif s == 'SELL' and d == 'BEARISH': return 15
        elif s == 'SELL': return 30
        return 50
    
    def _score_vwap(self, v):
        if not v: return 50
        s = v.get('signal', 'NEUTRAL')
        d = safe_float(v.get('deviation', 0))
        if s == 'BULLISH': return 75 if d > 3 else 65
        elif s == 'BEARISH': return 25 if d < -3 else 35
        return 50


class StopLossCalculator:
    @staticmethod
    def calculate_targets(indicators, recommendation):
        price = safe_float(indicators.get('current_price', 0))
        atr = safe_float(indicators.get('atr', 0))
        if atr == 0: atr = price * 0.02
        if price <= 0: return {'current_price': 0, 'atr': 0}
        
        result = {'current_price': round(price, 2), 'atr': round(atr, 2)}
        
        if recommendation in ['STRONG BUY', 'BUY']:
            sl = price - (atr * 1.5)
            result.update({
                'stop_loss': round(sl, 2), 'target1': round(price + atr * 1.5, 2),
                'target2': round(price + atr * 2.5, 2), 'target3': round(price + atr * 4, 2),
                'risk_amount': round(price - sl, 2), 'reward_amount': round(atr * 2.5, 2),
                'position': 'LONG (Buy)'
            })
        elif recommendation in ['SELL', 'STRONG SELL']:
            sl = price + (atr * 1.5)
            result.update({
                'stop_loss': round(sl, 2), 'target1': round(price - atr * 1.5, 2),
                'target2': round(price - atr * 2.5, 2), 'target3': round(price - atr * 4, 2),
                'risk_amount': round(sl - price, 2), 'reward_amount': round(atr * 2.5, 2),
                'position': 'SHORT (Sell)'
            })
        else:
            sl = price - (atr * 1.5)
            result.update({
                'stop_loss': round(sl, 2), 'target1': round(price + atr * 1.5, 2),
                'target2': round(price + atr * 2.5, 2), 'target3': round(price - atr * 2.5, 2),
                'risk_amount': round(price - sl, 2), 'reward_amount': round(atr * 1.5, 2),
                'position': 'HOLD (Neutral)'
            })
        
        ra, rw = result.get('risk_amount', 0), result.get('reward_amount', 0)
        result['risk_reward'] = round(rw / ra, 2) if ra > 0 else 0
        return result


# ============================================================
# TOOLTIPS
# ============================================================

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
    
    def show(self, event=None):
        x, y = self.widget.winfo_rootx() + 25, self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, background="#ffffdd", foreground="#333333",
                        relief=tk.SOLID, borderwidth=1, font=("Segoe UI", 9), padx=8, pady=4)
        label.pack()
    
    def hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


# ============================================================
# MAIN APPLICATION
# ============================================================

class StockScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DR. SHAH'S Analysis - Stock Technical Scanner v3.0")
        self.root.geometry("1500x950")
        self.root.minsize(1300, 850)
        
        self.theme = 'dark'
        self.colors = THEMES[self.theme]
        
        self.analyzer = TechnicalAnalyzer()
        self.scorer = StockScorer()
        self.gui_manager = ThreadSafeGUI(root)
        self.watchlist = []
        self.results = []
        self.is_scanning = False
        self.watchlist_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.json")
        self.load_watchlist()
        
        self.apply_theme()
        self.create_widgets()
        self.update_watchlist_display()
        self.update_dashboard()
        self.center_window()
        
        logger.info("App started v3.0")
    
    def center_window(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f'{w}x{h}+{x}+{y}')
    
    def apply_theme(self):
        c = self.colors
        self.root.configure(bg=c['bg_primary'])
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except:
            pass
        
        style.configure('.', background=c['bg_primary'], foreground=c['fg_primary'])
        style.configure('TNotebook', background=c['bg_primary'], borderwidth=0)
        style.configure('TNotebook.Tab', background=c['bg_secondary'], foreground=c['fg_primary'],
                        padding=[12, 6], font=('Segoe UI', 10))
        style.map('TNotebook.Tab', background=[('selected', c['bg_card'])], foreground=[('selected', c['fg_accent'])])
        style.configure('Treeview', background=c['bg_card'], foreground=c['fg_primary'],
                        fieldbackground=c['bg_card'], font=('Segoe UI', 10), rowheight=28)
        style.configure('Treeview.Heading', background=c['bg_secondary'], foreground=c['fg_accent'],
                        font=('Segoe UI', 10, 'bold'))
        style.map('Treeview', background=[('selected', c['selected'])], foreground=[('selected', 'white')])
        style.configure('TProgressbar', background=c['fg_accent'], troughcolor=c['bg_secondary'])
    
    def create_widgets(self):
        c = self.colors
        
        # Main container
        main = tk.Frame(self.root, bg=c['bg_primary'])
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        # Header with theme toggle
        header = tk.Frame(main, bg=c['bg_secondary'], height=60)
        header.pack(fill=tk.X, pady=(0, 8))
        header.pack_propagate(False)
        
        tk.Label(header, text="DR. SHAH'S Analysis", bg=c['bg_secondary'], fg=c['fg_accent'],
                font=('Segoe UI', 18, 'bold')).pack(side=tk.LEFT, padx=15)
        
        tk.Label(header, text="v3.0", bg=c['bg_secondary'], fg=c['fg_secondary'],
                font=('Segoe UI', 10)).pack(side=tk.LEFT)
        
        # Theme toggle button
        theme_text = "Light Mode" if self.theme == 'dark' else "Dark Mode"
        self.theme_btn = tk.Button(header, text=theme_text, bg=c['button_info'], fg='white',
                                  font=('Segoe UI', 9, 'bold'), relief=tk.FLAT, padx=12, pady=4,
                                  command=self.toggle_theme, cursor='hand2')
        self.theme_btn.pack(side=tk.RIGHT, padx=15)
        ToolTip(self.theme_btn, "Switch between dark and light theme")
        
        # Dashboard
        self.create_dashboard(main)
        
        # Control panel
        control = tk.Frame(main, bg=c['bg_secondary'], relief=tk.FLAT, bd=0)
        control.pack(fill=tk.X, pady=(0, 8))
        
        # Watchlist controls
        wl_frame = tk.LabelFrame(control, text="Watchlist", bg=c['bg_secondary'], fg=c['fg_accent'],
                                font=('Segoe UI', 10, 'bold'), bd=0)
        wl_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        entry_row = tk.Frame(wl_frame, bg=c['bg_secondary'])
        entry_row.pack(fill=tk.X, padx=8, pady=4)
        
        tk.Label(entry_row, text="Symbol:", bg=c['bg_secondary'], fg=c['fg_primary'],
                font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=4)
        
        self.stock_entry = tk.Entry(entry_row, font=('Segoe UI', 11), bg=c['bg_input'], fg=c['fg_primary'],
                                   insertbackground=c['fg_primary'], relief=tk.FLAT, width=12)
        self.stock_entry.pack(side=tk.LEFT, padx=4)
        self.stock_entry.bind('<Return>', lambda e: self.add_stock())
        ToolTip(self.stock_entry, "Enter NSE stock symbol (e.g., RELIANCE, TCS)")
        
        btn_row = tk.Frame(wl_frame, bg=c['bg_secondary'])
        btn_row.pack(fill=tk.X, padx=8, pady=4)
        
        for text, cmd, color in [("Add", self.add_stock, c['button_primary']),
                                  ("Delete", self.delete_stock, c['button_danger']),
                                  ("Clear", self.clear_watchlist, c['button_secondary'])]:
            btn = tk.Button(btn_row, text=text, bg=color, fg='white', font=('Segoe UI', 9, 'bold'),
                           relief=tk.FLAT, padx=10, pady=3, command=cmd, cursor='hand2')
            btn.pack(side=tk.LEFT, padx=3)
            btn.bind("<Enter>", lambda e, b=btn, cl=color: b.configure(bg=self.lighten_color(cl)))
            btn.bind("<Leave>", lambda e, b=btn, cl=color: b.configure(bg=cl))
        
        # Import/Export
        io_frame = tk.LabelFrame(control, text="Import / Export", bg=c['bg_secondary'], fg=c['fg_accent'],
                                font=('Segoe UI', 10, 'bold'), bd=0)
        io_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        io_row = tk.Frame(io_frame, bg=c['bg_secondary'])
        io_row.pack(fill=tk.X, padx=8, pady=8)
        
        for text, cmd, tip in [("Import", self.import_watchlist, "Import from Excel/PDF/JSON/CSV/TXT"),
                                ("Save List", self.save_watchlist_dialog, "Save watchlist to file"),
                                ("Load List", self.load_watchlist_dialog, "Load watchlist from file"),
                                ("Export Results", self.export_results, "Export scan results to Excel")]:
            btn = tk.Button(io_row, text=text, bg=c['button_info'], fg='white', font=('Segoe UI', 9, 'bold'),
                           relief=tk.FLAT, padx=10, pady=3, command=cmd, cursor='hand2')
            btn.pack(side=tk.LEFT, padx=3)
            ToolTip(btn, tip)
        
        # Scan controls
        scan_frame = tk.LabelFrame(control, text="Scan", bg=c['bg_secondary'], fg=c['fg_accent'],
                                  font=('Segoe UI', 10, 'bold'), bd=0)
        scan_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        scan_row = tk.Frame(scan_frame, bg=c['bg_secondary'])
        scan_row.pack(fill=tk.X, padx=8, pady=8)
        
        self.scan_btn = tk.Button(scan_row, text="SCAN ALL", bg=c['fg_danger'], fg='white',
                                 font=('Segoe UI', 11, 'bold'), relief=tk.FLAT, padx=15, pady=5,
                                 command=self.start_scan, cursor='hand2')
        self.scan_btn.pack(side=tk.LEFT, padx=5)
        ToolTip(self.scan_btn, "Scan all stocks in watchlist (F5)")
        
        self.progress = ttk.Progressbar(scan_row, mode='determinate', length=120)
        self.progress.pack(side=tk.LEFT, padx=10)
        
        self.status_label = tk.Label(scan_row, text="Ready", bg=c['bg_secondary'], fg=c['fg_secondary'],
                                    font=('Segoe UI', 9))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Notebook
        notebook_frame = tk.Frame(main, bg=c['bg_primary'])
        notebook_frame.pack(fill=tk.BOTH, expand=True)
        
        self.notebook = ttk.Notebook(notebook_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self.create_watchlist_tab()
        self.create_results_tab()
        self.create_breakdown_tab()
        self.create_targets_tab()
        
        # Status bar
        self.create_status_bar(main)
        
        # Keyboard shortcuts
        self.root.bind('<F5>', lambda e: self.start_scan())
        self.root.bind('<Control-i>', lambda e: self.import_watchlist())
        self.root.bind('<Control-e>', lambda e: self.export_results())
        self.root.bind('<Delete>', lambda e: self.delete_stock())
    
    def lighten_color(self, color, factor=0.2):
        """Lighten a hex color."""
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            r = min(255, int(r + (255 - r) * factor))
            g = min(255, int(g + (255 - g) * factor))
            b = min(255, int(b + (255 - b) * factor))
            return f'#{r:02x}{g:02x}{b:02x}'
        except:
            return color
    
    def toggle_theme(self):
        self.theme = 'light' if self.theme == 'dark' else 'dark'
        self.colors = THEMES[self.theme]
        self.apply_theme()
        
        # Destroy and recreate all widgets
        for widget in self.root.winfo_children():
            widget.destroy()
        self.create_widgets()
        self.update_watchlist_display()
        self.update_dashboard()
        if self.results:
            for r in self.results:
                self.add_result_to_tree(r)
    
    def create_dashboard(self, parent):
        c = self.colors
        self.dashboard = tk.Frame(parent, bg=c['bg_primary'])
        self.dashboard.pack(fill=tk.X, pady=(0, 8))
        
        # Dashboard cards
        self.dash_cards = {}
        cards_data = [
            ('total', 'Total Stocks', '0', c['fg_info']),
            ('strong_buy', 'Strong Buy', '0', '#238636'),
            ('buy', 'Buy', '0', c['fg_success']),
            ('hold', 'Hold', '0', c['fg_warning']),
            ('sell', 'Sell', '0', '#f97583'),
            ('strong_sell', 'Strong Sell', '0', c['fg_danger']),
            ('avg_score', 'Avg Score', '0', c['fg_accent']),
        ]
        
        for key, label, value, color in cards_data:
            card = tk.Frame(self.dashboard, bg=c['bg_card'], relief=tk.FLAT, bd=0)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
            
            tk.Label(card, text=label, bg=c['bg_card'], fg=c['fg_secondary'],
                    font=('Segoe UI', 9)).pack(pady=(8, 2))
            
            val_label = tk.Label(card, text=value, bg=c['bg_card'], fg=color,
                               font=('Segoe UI', 20, 'bold'))
            val_label.pack(pady=(0, 8))
            
            self.dash_cards[key] = val_label
    
    def update_dashboard(self):
        c = self.colors
        
        if not self.results:
            for key in self.dash_cards:
                self.dash_cards[key].configure(text='0')
            return
        
        total = len(self.results)
        sb = sum(1 for r in self.results if r['recommendation'] == 'STRONG BUY')
        buy = sum(1 for r in self.results if r['recommendation'] == 'BUY')
        hold = sum(1 for r in self.results if r['recommendation'] == 'HOLD')
        sell = sum(1 for r in self.results if r['recommendation'] == 'SELL')
        ss = sum(1 for r in self.results if r['recommendation'] == 'STRONG SELL')
        avg = sum(r['score'] for r in self.results) / total if total > 0 else 0
        
        self.dash_cards['total'].configure(text=str(total))
        self.dash_cards['strong_buy'].configure(text=str(sb))
        self.dash_cards['buy'].configure(text=str(buy))
        self.dash_cards['hold'].configure(text=str(hold))
        self.dash_cards['sell'].configure(text=str(sell))
        self.dash_cards['strong_sell'].configure(text=str(ss))
        self.dash_cards['avg_score'].configure(text=f"{avg:.1f}")
    
    def create_status_bar(self, parent):
        c = self.colors
        status = tk.Frame(parent, bg=c['bg_secondary'], height=28)
        status.pack(fill=tk.X, pady=(8, 0))
        status.pack_propagate(False)
        
        # Market status
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()
        if weekday < 5 and 9 <= hour < 16:
            market_status = "Market: OPEN"
            market_color = c['fg_success']
        else:
            market_status = "Market: CLOSED"
            market_color = c['fg_danger']
        
        tk.Label(status, text=market_status, bg=c['bg_secondary'], fg=market_color,
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=15)
        
        tk.Label(status, text=f"Last Scan: Never", bg=c['bg_secondary'], fg=c['fg_secondary'],
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=15)
        
        self.last_scan_label = status.winfo_children()[-1]
        
        tk.Label(status, text=f"Cache: 0 items", bg=c['bg_secondary'], fg=c['fg_secondary'],
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=15)
        
        self.cache_label = status.winfo_children()[-1]
        
        tk.Label(status, text=f"Theme: {self.theme.title()}", bg=c['bg_secondary'], fg=c['fg_secondary'],
                font=('Segoe UI', 9)).pack(side=tk.RIGHT, padx=15)
        
        tk.Label(status, text="F5=Scan | Ctrl+I=Import | Ctrl+E=Export | Del=Delete",
                bg=c['bg_secondary'], fg=c['fg_secondary'], font=('Segoe UI', 9)).pack(side=tk.RIGHT, padx=15)
    
    def create_watchlist_tab(self):
        c = self.colors
        tab = tk.Frame(self.notebook, bg=c['bg_primary'])
        self.notebook.add(tab, text="Watchlist")
        
        # Category filter
        filter_frame = tk.Frame(tab, bg=c['bg_secondary'])
        filter_frame.pack(fill=tk.X, padx=8, pady=4)
        
        tk.Label(filter_frame, text="Filter by Sector:", bg=c['bg_secondary'], fg=c['fg_primary'],
                font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=8)
        
        self.sector_var = tk.StringVar(value="All")
        sectors = ["All"] + list(SECTOR_MAP.keys()) + ["Custom"]
        sector_menu = ttk.Combobox(filter_frame, textvariable=self.sector_var, values=sectors,
                                   state='readonly', width=15)
        sector_menu.pack(side=tk.LEFT, padx=8)
        sector_menu.bind("<<ComboboxSelected>>", lambda e: self.filter_watchlist())
        ToolTip(sector_menu, "Filter watchlist by sector")
        
        list_frame = tk.Frame(tab, bg=c['bg_primary'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.watchlist_listbox = tk.Listbox(list_frame, bg=c['bg_input'], fg=c['fg_accent'],
                                           font=('Consolas', 12), selectbackground=c['selected'],
                                           selectforeground='white', yscrollcommand=scrollbar.set,
                                           relief=tk.FLAT)
        self.watchlist_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.watchlist_listbox.yview)
        
        # Right-click menu
        self.watchlist_menu = tk.Menu(self.root, tearoff=0)
        self.watchlist_menu.add_command(label="Delete Selected", command=self.delete_stock)
        self.watchlist_menu.add_command(label="Clear All", command=self.clear_watchlist)
        self.watchlist_menu.add_separator()
        self.watchlist_menu.add_command(label="Add to Favorites", command=lambda: None)
        
        self.watchlist_listbox.bind("<Button-3>", self.show_watchlist_menu)
        
        self.count_label = tk.Label(tab, text="Stocks: 0", bg=c['bg_primary'], fg=c['fg_secondary'],
                                   font=('Segoe UI', 10))
        self.count_label.pack(pady=4)
    
    def show_watchlist_menu(self, event):
        try:
            self.watchlist_listbox.selection_set(self.watchlist_listbox.nearest(event.y))
            self.watchlist_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.watchlist_menu.grab_release()
    
    def filter_watchlist(self):
        sector = self.sector_var.get()
        self.watchlist_listbox.delete(0, tk.END)
        
        if sector == "All":
            stocks = sorted(self.watchlist)
        elif sector in SECTOR_MAP:
            stocks = sorted([s for s in self.watchlist if s in SECTOR_MAP[sector]])
        else:
            stocks = sorted(self.watchlist)
        
        for stock in stocks:
            self.watchlist_listbox.insert(tk.END, stock)
        
        self.count_label.configure(text=f"Stocks: {len(stocks)}")
    
    def create_results_tab(self):
        c = self.colors
        tab = tk.Frame(self.notebook, bg=c['bg_primary'])
        self.notebook.add(tab, text="Scan Results")
        
        columns = ('Symbol', 'Price', 'Change%', 'RSI', 'SuperTrend', 'VWAP', 'Score', 'Recommendation')
        
        tree_frame = tk.Frame(tab, bg=c['bg_primary'])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        scrollbar_y = tk.Scrollbar(tree_frame)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x = tk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.results_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                        yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        for col in columns:
            self.results_tree.heading(col, text=col, anchor=tk.CENTER)
            self.results_tree.column(col, width=100, anchor=tk.CENTER)
        
        self.results_tree.pack(fill=tk.BOTH, expand=True)
        scrollbar_y.config(command=self.results_tree.yview)
        scrollbar_x.config(command=self.results_tree.xview)
        
        self.results_tree.bind('<Double-1>', self.show_breakdown)
        
        # Right-click menu
        self.results_menu = tk.Menu(self.root, tearoff=0)
        self.results_menu.add_command(label="View Details", command=lambda: self.show_breakdown(None))
        self.results_menu.add_command(label="Copy Symbol", command=self.copy_symbol)
        self.results_tree.bind("<Button-3>", self.show_results_menu)
    
    def show_results_menu(self, event):
        try:
            item = self.results_tree.identify_row(event.y)
            if item:
                self.results_tree.selection_set(item)
                self.results_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.results_menu.grab_release()
    
    def copy_symbol(self):
        selection = self.results_tree.selection()
        if selection:
            symbol = self.results_tree.item(selection[0])['values'][0]
            self.root.clipboard_clear()
            self.root.clipboard_append(symbol)
    
    def create_breakdown_tab(self):
        c = self.colors
        tab = tk.Frame(self.notebook, bg=c['bg_primary'])
        self.notebook.add(tab, text="Score Breakdown")
        
        self.breakdown_canvas = tk.Canvas(tab, bg=c['bg_primary'], highlightthickness=0)
        self.breakdown_scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self.breakdown_canvas.yview)
        self.breakdown_frame = tk.Frame(self.breakdown_canvas, bg=c['bg_primary'])
        
        self.breakdown_frame.bind("<Configure>", 
            lambda e: self.breakdown_canvas.configure(scrollregion=self.breakdown_canvas.bbox("all")))
        self.breakdown_canvas.create_window((0, 0), window=self.breakdown_frame, anchor="nw")
        self.breakdown_canvas.configure(yscrollcommand=self.breakdown_scrollbar.set)
        
        self.breakdown_scrollbar.pack(side="right", fill="y")
        self.breakdown_canvas.pack(side="left", fill="both", expand=True)
        
        tk.Label(self.breakdown_frame, text="Double-click a stock to view breakdown",
                bg=c['bg_primary'], fg=c['fg_accent'], font=('Segoe UI', 14, 'bold')).pack(pady=50)
    
    def create_targets_tab(self):
        c = self.colors
        tab = tk.Frame(self.notebook, bg=c['bg_primary'])
        self.notebook.add(tab, text="Stop-Loss & Targets")
        
        self.targets_canvas = tk.Canvas(tab, bg=c['bg_primary'], highlightthickness=0)
        self.targets_scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self.targets_canvas.yview)
        self.targets_frame = tk.Frame(self.targets_canvas, bg=c['bg_primary'])
        
        self.targets_frame.bind("<Configure>", 
            lambda e: self.targets_canvas.configure(scrollregion=self.targets_canvas.bbox("all")))
        self.targets_canvas.create_window((0, 0), window=self.targets_frame, anchor="nw")
        self.targets_canvas.configure(yscrollcommand=self.targets_scrollbar.set)
        
        self.targets_scrollbar.pack(side="right", fill="y")
        self.targets_canvas.pack(side="left", fill="both", expand=True)
        
        tk.Label(self.targets_frame, text="Double-click a stock to view targets",
                bg=c['bg_primary'], fg=c['fg_accent'], font=('Segoe UI', 14, 'bold')).pack(pady=50)
    
    def add_stock(self):
        symbol = self.stock_entry.get().strip().upper()
        if not symbol:
            messagebox.showwarning("Warning", "Enter a stock symbol!")
            return
        symbol = re.sub(r'[^A-Z0-9&-]', '', symbol)
        if not symbol:
            messagebox.showwarning("Warning", "Invalid symbol!")
            return
        if symbol in self.watchlist:
            messagebox.showinfo("Info", f"{symbol} already in watchlist!")
            return
        self.watchlist.append(symbol)
        self.stock_entry.delete(0, tk.END)
        self.update_watchlist_display()
        self.save_watchlist()
    
    def delete_stock(self):
        sel = self.watchlist_listbox.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Select a stock to delete!")
            return
        symbol = self.watchlist_listbox.get(sel[0])
        if symbol in self.watchlist:
            self.watchlist.remove(symbol)
        self.update_watchlist_display()
        self.save_watchlist()
    
    def clear_watchlist(self):
        if messagebox.askyesno("Confirm", "Clear entire watchlist?"):
            self.watchlist.clear()
            self.update_watchlist_display()
            self.save_watchlist()
    
    def update_watchlist_display(self):
        self.watchlist_listbox.delete(0, tk.END)
        for stock in sorted(self.watchlist):
            self.watchlist_listbox.insert(tk.END, stock)
        self.count_label.configure(text=f"Stocks: {len(self.watchlist)}")
    
    def save_watchlist(self):
        try:
            with open(self.watchlist_file, 'w') as f:
                json.dump(self.watchlist, f)
        except:
            pass
    
    def load_watchlist(self):
        try:
            if os.path.exists(self.watchlist_file):
                with open(self.watchlist_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.watchlist = data
        except:
            self.watchlist = []
    
    def import_watchlist(self):
        filetypes = [("All Supported", "*.xlsx *.xls *.pdf *.json *.csv *.txt"),
                    ("Excel files", "*.xlsx *.xls"), ("PDF files", "*.pdf"),
                    ("JSON files", "*.json"), ("CSV files", "*.csv"), ("Text files", "*.txt")]
        
        filepath = filedialog.askopenfilename(title="Import Watchlist", filetypes=filetypes)
        if not filepath:
            return
        
        imported = []
        ext = os.path.splitext(filepath)[1].lower()
        
        try:
            if ext in ('.xlsx', '.xls'):
                df = pd.read_excel(filepath, header=None)
                for col in df.columns:
                    for val in df[col].dropna():
                        s = str(val).strip().upper()
                        if s and len(s) >= 2 and s.replace('-', '').isalpha():
                            imported.append(s)
            elif ext == '.pdf':
                if not PDFPLUMBER_AVAILABLE:
                    messagebox.showerror("Error", "Install pdfplumber: pip install pdfplumber")
                    return
                with pdfplumber.open(filepath) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            for word in text.split():
                                s = re.sub(r'[^A-Za-z0-9&-]', '', word.strip()).upper()
                                if s and len(s) >= 2 and s.isalpha() and len(s) <= 15:
                                    imported.append(s)
            elif ext == '.json':
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        imported = [str(s).strip().upper() for s in data]
            elif ext == '.csv':
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    for row in csv.reader(f):
                        if row and row[0].strip():
                            imported.append(row[0].strip().upper())
            elif ext == '.txt':
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    for line in f:
                        s = line.strip().upper()
                        if s:
                            imported.append(s)
            
            added = 0
            for s in set(imported):
                if s not in self.watchlist and len(s) >= 2:
                    self.watchlist.append(s)
                    added += 1
            
            self.update_watchlist_display()
            self.save_watchlist()
            messagebox.showinfo("Import", f"Added {added} new stocks from {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {e}")
    
    def save_watchlist_dialog(self):
        """Save watchlist to a user-selected file."""
        if not self.watchlist:
            messagebox.showwarning("Warning", "Watchlist is empty!")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Save Watchlist",
            defaultextension=".json",
            initialfile="my_watchlist.json",
            filetypes=[
                ("JSON files", "*.json"),
                ("CSV files", "*.csv"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if not filepath:
            return
        
        try:
            if filepath.endswith('.json'):
                data = {
                    'watchlist': self.watchlist,
                    'saved_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'app_name': "DR. SHAH'S Analysis",
                    'total_stocks': len(self.watchlist)
                }
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2)
            
            elif filepath.endswith('.csv'):
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Symbol', 'Added Date'])
                    for symbol in self.watchlist:
                        writer.writerow([symbol, datetime.now().strftime('%Y-%m-%d')])
            
            else:  # .txt
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"DR. SHAH'S Analysis - Watchlist\n")
                    f.write(f"Saved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Total Stocks: {len(self.watchlist)}\n")
                    f.write("-" * 30 + "\n")
                    for symbol in sorted(self.watchlist):
                        f.write(f"{symbol}\n")
            
            messagebox.showinfo("Success", 
                              f"Watchlist saved successfully!\n\n"
                              f"File: {os.path.basename(filepath)}\n"
                              f"Stocks: {len(self.watchlist)}")
            logger.info(f"Watchlist saved to {filepath}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
            logger.error(f"Save error: {e}")
    
    def load_watchlist_dialog(self):
        """Load watchlist from a user-selected file."""
        filepath = filedialog.askopenfilename(
            title="Load Watchlist",
            filetypes=[
                ("JSON files", "*.json"),
                ("CSV files", "*.csv"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if not filepath:
            return
        
        try:
            imported = []
            
            if filepath.endswith('.json'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'watchlist' in data:
                        imported = [str(s).strip().upper() for s in data['watchlist'] if str(s).strip()]
                    elif isinstance(data, list):
                        imported = [str(s).strip().upper() for s in data if str(s).strip()]
            
            elif filepath.endswith('.csv'):
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)  # Skip header
                    for row in reader:
                        if row and row[0].strip():
                            imported.append(row[0].strip().upper())
            
            else:  # .txt
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    for line in f:
                        s = line.strip().upper()
                        if s and len(s) >= 2 and not s.startswith('#') and not s.startswith('-'):
                            # Skip header lines
                            if not any(word in s for word in ['WATCHLIST', 'SAVED', 'TOTAL', 'DR.', 'SHAHS', 'ANALYSIS']):
                                imported.append(s)
            
            if not imported:
                messagebox.showinfo("Info", "No stocks found in file!")
                return
            
            # Ask merge or replace
            choice = messagebox.askyesnocancel(
                "Load Watchlist",
                f"Found {len(imported)} stocks in file.\n\n"
                f"Yes = Merge with current watchlist\n"
                f"No = Replace current watchlist\n"
                f"Cancel = Cancel"
            )
            
            if choice is None:  # Cancel
                return
            
            if choice:  # Merge
                added = 0
                for s in imported:
                    if s not in self.watchlist:
                        self.watchlist.append(s)
                        added += 1
                messagebox.showinfo("Merged", f"Added {added} new stocks. Total: {len(self.watchlist)}")
            else:  # Replace
                self.watchlist = list(set(imported))
                messagebox.showinfo("Loaded", f"Loaded {len(self.watchlist)} stocks")
            
            self.update_watchlist_display()
            self.save_watchlist()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")
            logger.error(f"Load error: {e}")
    
    def export_watchlist(self):
        if not self.watchlist:
            messagebox.showwarning("Warning", "Watchlist is empty!")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".json",
                                               filetypes=[("JSON", "*.json"), ("CSV", "*.csv"), ("Text", "*.txt")])
        if not filepath:
            return
        try:
            if filepath.endswith('.json'):
                with open(filepath, 'w') as f:
                    json.dump(self.watchlist, f, indent=2)
            elif filepath.endswith('.csv'):
                with open(filepath, 'w', newline='') as f:
                    csv.writer(f).writerows([[s] for s in self.watchlist])
            else:
                with open(filepath, 'w') as f:
                    f.write('\n'.join(self.watchlist))
            messagebox.showinfo("Success", f"Exported to {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def export_results(self):
        if not self.results:
            messagebox.showwarning("Warning", "No results! Run a scan first.")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                               filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")])
        if not filepath:
            return
        try:
            if filepath.endswith('.xlsx'):
                wb = Workbook()
                ws = wb.active
                ws.title = "DR. SHAH'S Analysis"
                headers = ['Symbol', 'Price', 'Change%', 'RSI', 'Score', 'Recommendation',
                          'Stop Loss', 'Target 1', 'Target 2', 'Risk:Reward']
                for i, h in enumerate(headers, 1):
                    cell = ws.cell(row=1, column=i, value=h)
                    cell.font = Font(bold=True)
                for row, r in enumerate(self.results, 2):
                    t = r.get('targets', {})
                    ws.cell(row=row, column=1, value=r['symbol'])
                    ws.cell(row=row, column=2, value=round(r['price'], 2))
                    ws.cell(row=row, column=3, value=round(r['change'], 2))
                    ws.cell(row=row, column=4, value=round(r['rsi'], 2))
                    ws.cell(row=row, column=5, value=r['score'])
                    ws.cell(row=row, column=6, value=r['recommendation'])
                    ws.cell(row=row, column=7, value=t.get('stop_loss', ''))
                    ws.cell(row=row, column=8, value=t.get('target1', ''))
                    ws.cell(row=row, column=9, value=t.get('target2', ''))
                    ws.cell(row=row, column=10, value=f"1:{t.get('risk_reward', 0)}")
                wb.save(filepath)
            else:
                with open(filepath, 'w', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(['Symbol', 'Price', 'Score', 'Recommendation'])
                    for r in self.results:
                        w.writerow([r['symbol'], round(r['price'], 2), r['score'], r['recommendation']])
            messagebox.showinfo("Success", f"Exported to {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def start_scan(self):
        if not self.watchlist:
            messagebox.showwarning("Warning", "Watchlist is empty!")
            return
        if self.is_scanning:
            return
        self.is_scanning = True
        self.scan_btn.configure(state=tk.DISABLED, text="SCANNING...")
        self.results = []
        self.results_tree.delete(*self.results_tree.get_children())
        threading.Thread(target=self.scan_stocks, daemon=True).start()
    
    def scan_stocks(self):
        total = len(self.watchlist)
        for idx, symbol in enumerate(self.watchlist):
            try:
                self.gui_manager.schedule(self.update_status, f"Scanning {symbol} ({idx+1}/{total})", (idx/total)*100)
                df = self.analyzer.fetch_stock_data(symbol)
                if df is None or df.empty or len(df) < 30:
                    continue
                indicators = self.analyzer.calculate_all_indicators(df)
                score_data = self.scorer.calculate_total_score(indicators)
                prev = safe_float(indicators['prev_close'])
                price = safe_float(indicators['current_price'])
                change = ((price - prev) / prev * 100) if prev > 0 else 0
                targets = StopLossCalculator.calculate_targets(indicators, score_data['recommendation'])
                st = indicators.get('supertrend', {})
                vwap = indicators.get('vwap', {})
                result = {
                    'symbol': symbol, 'price': price, 'change': change,
                    'rsi': safe_float(indicators['rsi']),
                    'macd': safe_float(indicators['macd']['histogram']),
                    'macd_signal': 'Bullish' if safe_float(indicators['macd']['histogram']) > 0 else 'Bearish',
                    'score': score_data['total'], 'recommendation': score_data['recommendation'],
                    'breakdown': score_data['breakdown'], 'indicators': indicators, 'targets': targets,
                    'supertrend_signal': st.get('signal', 'N/A'), 'supertrend_direction': st.get('direction', 'N/A'),
                    'vwap_signal': vwap.get('signal', 'N/A')
                }
                self.results.append(result)
                self.gui_manager.schedule(self.add_result_to_tree, result)
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Scan error {symbol}: {e}")
        
        self.results.sort(key=lambda x: x['score'], reverse=True)
        self.gui_manager.schedule(self.scan_complete)
    
    def update_status(self, msg, progress):
        self.status_label.configure(text=msg)
        self.progress['value'] = progress
    
    def add_result_to_tree(self, r):
        tags = {'STRONG BUY': 'sb', 'BUY': 'buy', 'HOLD': 'hold', 'SELL': 'sell', 'STRONG SELL': 'ss'}
        tag = tags.get(r['recommendation'], '')
        self.results_tree.insert('', tk.END, values=(
            r['symbol'], f"{r['price']:.2f}", f"{r['change']:+.2f}%",
            f"{r['rsi']:.1f}", r.get('supertrend_signal', 'N/A'), r.get('vwap_signal', 'N/A'),
            f"{r['score']:.1f}", r['recommendation']
        ), tags=(tag,))
        
        c = self.colors
        self.results_tree.tag_configure('sb', background='#238636', foreground='white')
        self.results_tree.tag_configure('buy', background='#2da44e', foreground='white')
        self.results_tree.tag_configure('hold', background='#9e6a03', foreground='white')
        self.results_tree.tag_configure('sell', background='#da3633', foreground='white')
        self.results_tree.tag_configure('ss', background='#b62324', foreground='white')
    
    def scan_complete(self):
        self.is_scanning = False
        self.scan_btn.configure(state=tk.NORMAL, text="SCAN ALL")
        self.progress['value'] = 100
        self.status_label.configure(text="Complete!")
        self.notebook.select(1)
        self.update_dashboard()
        self.last_scan_label.configure(text=f"Last Scan: {datetime.now().strftime('%H:%M:%S')}")
        
        cache_stats = self.analyzer.cache.cache
        self.cache_label.configure(text=f"Cache: {len(cache_stats)} items")
        
        messagebox.showinfo("Scan Complete", f"Scanned {len(self.results)} stocks!")
    
    def show_breakdown(self, event):
        sel = self.results_tree.selection()
        if not sel:
            return
        symbol = self.results_tree.item(sel[0])['values'][0]
        result = next((r for r in self.results if r['symbol'] == symbol), None)
        if not result:
            return
        self.update_breakdown_tab(result)
        self.update_targets_tab(result)
        self.notebook.select(2)
    
    def update_breakdown_tab(self, result):
        c = self.colors
        for w in self.breakdown_frame.winfo_children():
            w.destroy()
        
        symbol = result['symbol']
        score = result['score']
        color = '#238636' if score >= 75 else '#2da44e' if score >= 60 else '#9e6a03' if score >= 45 else '#da3633' if score >= 30 else '#b62324'
        
        tk.Label(self.breakdown_frame, text=f"Score Breakdown: {symbol}",
                bg=c['bg_primary'], fg=c['fg_accent'], font=('Segoe UI', 18, 'bold')).pack(pady=15)
        
        tk.Label(self.breakdown_frame, text=f"Score: {score}/100 - {result['recommendation']}",
                bg=c['bg_primary'], fg=color, font=('Segoe UI', 16, 'bold')).pack(pady=5)
        
        tk.Label(self.breakdown_frame, text=f"Price: {result['price']:.2f} | Change: {result['change']:+.2f}%",
                bg=c['bg_primary'], fg=c['fg_primary'], font=('Segoe UI', 12)).pack(pady=5)
        
        breakdown = result.get('breakdown', {})
        names = {'rsi': 'RSI (14)', 'macd': 'MACD', 'moving_averages': 'Moving Averages',
                'bollinger': 'Bollinger Bands', 'stochastic': 'Stochastic', 'adx': 'ADX (Trend)',
                'volume': 'Volume (OBV)', 'momentum': 'Momentum', 'supertrend': 'SuperTrend', 'vwap': 'VWAP'}
        
        bars_frame = tk.Frame(self.breakdown_frame, bg=c['bg_primary'])
        bars_frame.pack(fill=tk.X, padx=80, pady=20)
        
        for key, value in breakdown.items():
            row = tk.Frame(bars_frame, bg=c['bg_primary'])
            row.pack(fill=tk.X, pady=3)
            
            tk.Label(row, text=f"{names.get(key, key)}:", bg=c['bg_primary'], fg=c['fg_primary'],
                    font=('Segoe UI', 10), width=18, anchor=tk.W).pack(side=tk.LEFT, padx=5)
            
            bar = tk.Canvas(row, height=20, bg=c['bg_secondary'], highlightthickness=0)
            bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            bar_color = '#238636' if value >= 70 else '#2da44e' if value >= 50 else '#9e6a03' if value >= 30 else '#da3633'
            bar.create_rectangle(0, 0, int(value * 2), 20, fill=bar_color, outline='')
            
            tk.Label(row, text=f"{value}", bg=c['bg_primary'], fg=c['fg_primary'],
                    font=('Segoe UI', 10, 'bold'), width=6).pack(side=tk.LEFT, padx=5)
    
    def update_targets_tab(self, result):
        c = self.colors
        for w in self.targets_frame.winfo_children():
            w.destroy()
        
        symbol = result['symbol']
        targets = result.get('targets', {})
        rec = result.get('recommendation', 'HOLD')
        price = targets.get('current_price', 0)
        
        tk.Label(self.targets_frame, text=f"Stop-Loss & Targets: {symbol}",
                bg=c['bg_primary'], fg=c['fg_accent'], font=('Segoe UI', 18, 'bold')).pack(pady=15)
        
        tk.Label(self.targets_frame, text=f"Current Price: {price:.2f}",
                bg=c['bg_card'], fg=c['fg_primary'], font=('Segoe UI', 16, 'bold')).pack(pady=10, padx=80, fill=tk.X)
        
        rec_color = '#238636' if rec in ['STRONG BUY', 'BUY'] else '#da3633' if rec in ['SELL', 'STRONG SELL'] else '#9e6a03'
        tk.Label(self.targets_frame, text=f"{rec} | {targets.get('position', '')}",
                bg=c['bg_primary'], fg=rec_color, font=('Segoe UI', 14, 'bold')).pack(pady=5)
        
        # Stop Loss
        sl = targets.get('stop_loss', 0)
        sl_frame = tk.LabelFrame(self.targets_frame, text="STOP LOSS", bg=c['bg_card'], fg='#da3633',
                                font=('Segoe UI', 12, 'bold'))
        sl_frame.pack(fill=tk.X, padx=80, pady=10)
        tk.Label(sl_frame, text=f"{sl:.2f}", bg=c['bg_card'], fg='#da3633',
                font=('Segoe UI', 20, 'bold')).pack(pady=15)
        
        # Targets
        for label, val, color in [("TARGET 1 (Conservative)", targets.get('target1', 0), '#2da44e'),
                                   ("TARGET 2 (Moderate)", targets.get('target2', 0), '#238636'),
                                   ("TARGET 3 (Aggressive)", targets.get('target3', 0), '#58a6ff')]:
            frame = tk.LabelFrame(self.targets_frame, text=label, bg=c['bg_card'], fg=color,
                                 font=('Segoe UI', 11, 'bold'))
            frame.pack(fill=tk.X, padx=80, pady=5)
            tk.Label(frame, text=f"{val:.2f}" if val else "N/A", bg=c['bg_card'], fg=color,
                    font=('Segoe UI', 18, 'bold')).pack(pady=10)
        
        # Risk-Reward
        rr_frame = tk.LabelFrame(self.targets_frame, text="RISK-REWARD ANALYSIS", bg=c['bg_card'], fg='#d29922',
                                font=('Segoe UI', 14, 'bold'))
        rr_frame.pack(fill=tk.X, padx=80, pady=15)
        
        risk_amt = targets.get('risk_amount', 0) or 0
        reward_amt = targets.get('reward_amount', 0) or 0
        rr = targets.get('risk_reward', 0) or 0
        
        boxes = tk.Frame(rr_frame, bg=c['bg_card'])
        boxes.pack(fill=tk.X, pady=15, padx=20)
        
        # Risk box
        r_box = tk.Frame(boxes, bg='#da3633', relief=tk.RAISED, bd=2)
        r_box.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
        tk.Label(r_box, text="RISK", bg='#da3633', fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=5)
        tk.Label(r_box, text=f"{risk_amt:.2f}", bg='#da3633', fg='white', font=('Segoe UI', 18, 'bold')).pack(pady=5)
        if price > 0:
            tk.Label(r_box, text=f"{(risk_amt/price*100):.1f}%", bg='#da3633', fg='#ffcdd2', font=('Segoe UI', 10)).pack(pady=(0, 10))
        
        tk.Label(boxes, text="--->", bg=c['bg_card'], fg='white', font=('Segoe UI', 20, 'bold')).pack(side=tk.LEFT, padx=10)
        
        # Reward box
        rw_box = tk.Frame(boxes, bg='#238636', relief=tk.RAISED, bd=2)
        rw_box.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
        tk.Label(rw_box, text="REWARD", bg='#238636', fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=5)
        tk.Label(rw_box, text=f"{reward_amt:.2f}", bg='#238636', fg='white', font=('Segoe UI', 18, 'bold')).pack(pady=5)
        if price > 0:
            tk.Label(rw_box, text=f"{(reward_amt/price*100):.1f}%", bg='#238636', fg='#c6efce', font=('Segoe UI', 10)).pack(pady=(0, 10))
        
        # Ratio display
        rr_color = '#238636' if rr >= 2 else '#2da44e' if rr >= 1.5 else '#9e6a03' if rr >= 1 else '#da3633'
        quality = "EXCELLENT" if rr >= 2 else "GOOD" if rr >= 1.5 else "ACCEPTABLE" if rr >= 1 else "POOR"
        
        tk.Label(rr_frame, text="Risk : Reward", bg=c['bg_card'], fg=c['fg_secondary'],
                font=('Segoe UI', 12)).pack(pady=(15, 5))
        tk.Label(rr_frame, text=f"1 : {rr:.2f}" if rr > 0 else "N/A",
                bg=c['bg_card'], fg=rr_color, font=('Segoe UI', 28, 'bold')).pack(pady=5)
        tk.Label(rr_frame, text=f"Quality: {quality}", bg=c['bg_card'], fg=rr_color,
                font=('Segoe UI', 14, 'bold')).pack(pady=(5, 15))
        
        # Visual bar
        bar_frame = tk.Frame(rr_frame, bg=c['bg_card'])
        bar_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        bar_canvas = tk.Canvas(bar_frame, height=30, bg=c['bg_secondary'], highlightthickness=0)
        bar_canvas.pack(fill=tk.X)
        
        def draw_bar():
            bar_canvas.update_idletasks()
            w = max(bar_canvas.winfo_width(), 400)
            if risk_amt > 0 and reward_amt > 0:
                total = risk_amt + reward_amt
                rw = int(w * risk_amt / total)
                bar_canvas.delete("all")
                bar_canvas.create_rectangle(0, 0, rw, 30, fill='#da3633', outline='')
                bar_canvas.create_text(rw//2, 15, text=f"Risk {risk_amt/total*100:.0f}%", fill='white', font=('Segoe UI', 10, 'bold'))
                bar_canvas.create_rectangle(rw, 0, w, 30, fill='#238636', outline='')
                bar_canvas.create_text(rw + (w-rw)//2, 15, text=f"Reward {reward_amt/total*100:.0f}%", fill='white', font=('Segoe UI', 10, 'bold'))
        
        self.root.after(100, draw_bar)
        
        # Trading advice
        advice_frame = tk.LabelFrame(self.targets_frame, text="Trading Advice", bg=c['bg_card'], fg='#d29922',
                                    font=('Segoe UI', 11, 'bold'))
        advice_frame.pack(fill=tk.X, padx=80, pady=15)
        
        if rec in ['STRONG BUY', 'BUY']:
            advice = f"Enter: {price:.2f} | SL: {sl:.2f} | Target: {targets.get('target1', 0):.2f}\nRisk: {(risk_amt/price*100):.1f}% per trade"
        elif rec in ['SELL', 'STRONG SELL']:
            advice = f"Exit: {price:.2f} | SL: {sl:.2f} | Target: {targets.get('target1', 0):.2f}"
        else:
            advice = f"Support: {sl:.2f} | Resistance: {targets.get('target1', 0):.2f}\nWait for breakout"
        
        tk.Label(advice_frame, text=advice, bg=c['bg_card'], fg=c['fg_primary'],
                font=('Segoe UI', 11), justify=tk.LEFT).pack(padx=15, pady=15)
        
        self.notebook.select(3)


def main():
    try:
        root = tk.Tk()
        app = StockScannerApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
