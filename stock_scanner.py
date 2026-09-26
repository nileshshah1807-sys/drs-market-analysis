#!/usr/bin/env python3
"""
Indian Stock Technical Scanner & Recommender
=============================================
A desktop application that scans stocks from your watchlist using technical
analysis indicators, scores them 0-100, and gives buy/sell recommendations.

Version: 2.0 - Enhanced with caching, thread safety, more indicators
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
from functools import lru_cache

# Configure logging
logging.basicConfig(
    filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stock_scanner.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'
)
logger = logging.getLogger(__name__)

# Check Python version
if sys.version_info < (3, 7):
    print("ERROR: Python 3.7 or higher is required!")
    print(f"You are using Python {sys.version_info.major}.{sys.version_info.minor}")
    input("Press Enter to exit...")
    sys.exit(1)

# Third-party imports with error handling
try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance not installed!")
    print("Run: pip install yfinance")
    input("Press Enter to exit...")
    sys.exit(1)

try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("ERROR: pandas/numpy not installed!")
    print("Run: pip install pandas numpy")
    input("Press Enter to exit...")
    sys.exit(1)

try:
    import ta
except ImportError:
    print("ERROR: ta (technical analysis) not installed!")
    print("Run: pip install ta")
    input("Press Enter to exit...")
    sys.exit(1)

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
except ImportError:
    print("ERROR: openpyxl not installed!")
    print("Run: pip install openpyxl")
    input("Press Enter to exit...")
    sys.exit(1)

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
    logger.info("pdfplumber imported successfully")
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.warning("pdfplumber not available")
    
    # Try to auto-install pdfplumber
    try:
        import subprocess
        import sys as _sys
        print("pdfplumber not found. Attempting to install...")
        subprocess.check_call([_sys.executable, "-m", "pip", "install", "pdfplumber", "-q"])
        # Try importing again
        import pdfplumber
        PDFPLUMBER_AVAILABLE = True
        print("pdfplumber installed successfully!")
        logger.info("pdfplumber auto-installed successfully")
    except Exception as install_error:
        print(f"WARNING: Could not auto-install pdfplumber: {install_error}")
        print("PDF import will be disabled. To enable, run manually:")
        print(f"  {_sys.executable} -m pip install pdfplumber")

# Tkinter import with better error handling
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    print("ERROR: tkinter not available!")
    print("\nTo fix this:")
    print("  Windows: Reinstall Python with 'tcl/tk and IDLE' option checked")
    print("  Linux: sudo apt-get install python3-tk")
    print("  Mac: brew install python-tk")
    input("Press Enter to exit...")
    sys.exit(1)


def safe_float(value, default=0.0):
    """Safely convert value to float, handling NaN and None."""
    try:
        if value is None:
            return default
        val = float(value)
        if pd.isna(val) or np.isnan(val) or np.isinf(val):
            return default
        return val
    except (TypeError, ValueError):
        return default


def is_valid_number(value):
    """Check if value is a valid number (not NaN, None, or infinite)."""
    try:
        if value is None:
            return False
        val = float(value)
        return not (pd.isna(val) or np.isnan(val) or np.isinf(val))
    except (TypeError, ValueError):
        return False


class DataCache:
    """Cache for stock data to avoid repeated API calls."""
    
    def __init__(self, cache_duration_hours=4):
        self.cache = {}
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self._lock = threading.Lock()
        logger.info(f"DataCache initialized with {cache_duration_hours}h duration")
    
    def get(self, symbol):
        """Get cached data for symbol if available and not expired."""
        with self._lock:
            if symbol in self.cache:
                data, timestamp = self.cache[symbol]
                if datetime.now() - timestamp < self.cache_duration:
                    logger.debug(f"Cache hit for {symbol}")
                    return data
                else:
                    # Cache expired
                    del self.cache[symbol]
                    logger.debug(f"Cache expired for {symbol}")
            return None
    
    def set(self, symbol, data):
        """Cache data for symbol."""
        with self._lock:
            self.cache[symbol] = (data, datetime.now())
            logger.debug(f"Cached data for {symbol}")
    
    def clear(self):
        """Clear all cached data."""
        with self._lock:
            self.cache.clear()
            logger.info("Cache cleared")
    
    def get_stats(self):
        """Get cache statistics."""
        with self._lock:
            valid_count = sum(1 for _, (_, ts) in self.cache.items() 
                           if datetime.now() - ts < self.cache_duration)
            return {
                'total': len(self.cache),
                'valid': valid_count,
                'expired': len(self.cache) - valid_count
            }


class ThreadSafeGUI:
    """Thread-safe GUI update manager."""
    
    def __init__(self, root):
        self.root = root
        self.update_queue = queue.Queue()
        self._process_queue()
    
    def _process_queue(self):
        """Process pending GUI updates from queue."""
        try:
            while True:
                func, args, kwargs = self.update_queue.get_nowait()
                func(*args, **kwargs)
        except queue.Empty:
            pass
        # Schedule next check
        self.root.after(50, self._process_queue)
    
    def schedule(self, func, *args, **kwargs):
        """Schedule a GUI update to be executed on the main thread."""
        self.update_queue.put((func, args, kwargs))


class TechnicalAnalyzer:
    """Core technical analysis engine for Indian stocks."""
    
    def __init__(self):
        self.indicators = {}
        self.cache = DataCache(cache_duration_hours=4)
        
    def fetch_stock_data(self, symbol, period="1y"):
        """Fetch historical stock data from Yahoo Finance with caching."""
        # Check cache first
        cache_key = f"{symbol}_{period}"
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            logger.info(f"Using cached data for {symbol}")
            return cached_data
        
        try:
            # Try NSE first
            ticker = yf.Ticker(f"{symbol}.NS")
            df = ticker.history(period=period)
            
            if df is None or df.empty:
                # Try BSE if NSE fails
                ticker = yf.Ticker(f"{symbol}.BO")
                df = ticker.history(period=period)
            
            if df is None:
                return pd.DataFrame()
            
            # Cache the data
            if not df.empty:
                self.cache.set(cache_key, df)
                logger.info(f"Fetched and cached data for {symbol}: {len(df)} rows")
            
            return df
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            raise Exception(f"Failed to fetch data for {symbol}: {str(e)}")
    
    def calculate_rsi(self, df, period=14):
        """Calculate Relative Strength Index with NaN handling."""
        try:
            rsi = ta.momentum.RSIIndicator(df['Close'], window=period)
            result = rsi.rsi()
            if result.empty:
                return 50.0
            value = result.iloc[-1]
            return safe_float(value, 50.0)
        except Exception as e:
            logger.warning(f"RSI calculation error: {e}")
            return 50.0
    
    def calculate_macd(self, df):
        """Calculate MACD and signal line with NaN handling."""
        try:
            macd = ta.trend.MACD(df['Close'])
            return {
                'macd': safe_float(macd.macd().iloc[-1] if not macd.macd().empty else 0.0),
                'signal': safe_float(macd.macd_signal().iloc[-1] if not macd.macd_signal().empty else 0.0),
                'histogram': safe_float(macd.macd_diff().iloc[-1] if not macd.macd_diff().empty else 0.0)
            }
        except Exception as e:
            logger.warning(f"MACD calculation error: {e}")
            return {'macd': 0.0, 'signal': 0.0, 'histogram': 0.0}
    
    def calculate_moving_averages(self, df):
        """Calculate SMA 20, 50, 200 and EMA 12, 26 with NaN handling."""
        try:
            price = safe_float(df['Close'].iloc[-1])
            return {
                'sma_20': safe_float(ta.trend.SMAIndicator(df['Close'], window=20).sma_indicator().iloc[-1], price),
                'sma_50': safe_float(ta.trend.SMAIndicator(df['Close'], window=50).sma_indicator().iloc[-1], price) if len(df) >= 50 else price,
                'sma_200': safe_float(ta.trend.SMAIndicator(df['Close'], window=200).sma_indicator().iloc[-1], price) if len(df) >= 200 else price,
                'ema_12': safe_float(ta.trend.EMAIndicator(df['Close'], window=12).ema_indicator().iloc[-1], price),
                'ema_26': safe_float(ta.trend.EMAIndicator(df['Close'], window=26).ema_indicator().iloc[-1], price)
            }
        except Exception as e:
            logger.warning(f"Moving averages calculation error: {e}")
            price = safe_float(df['Close'].iloc[-1])
            return {'sma_20': price, 'sma_50': price, 'sma_200': price, 'ema_12': price, 'ema_26': price}
    
    def calculate_bollinger_bands(self, df):
        """Calculate Bollinger Bands with NaN handling."""
        try:
            bb = ta.volatility.BollingerBands(df['Close'])
            return {
                'upper': safe_float(bb.bollinger_hband().iloc[-1]),
                'middle': safe_float(bb.bollinger_mavg().iloc[-1]),
                'lower': safe_float(bb.bollinger_lband().iloc[-1]),
                'width': safe_float(bb.bollinger_wband().iloc[-1])
            }
        except Exception as e:
            logger.warning(f"Bollinger Bands calculation error: {e}")
            price = safe_float(df['Close'].iloc[-1])
            return {'upper': price * 1.02, 'middle': price, 'lower': price * 0.98, 'width': 0.04}
    
    def calculate_stochastic(self, df):
        """Calculate Stochastic Oscillator with NaN handling."""
        try:
            stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
            return {
                'k': safe_float(stoch.stoch().iloc[-1], 50.0),
                'd': safe_float(stoch.stoch_signal().iloc[-1], 50.0)
            }
        except Exception as e:
            logger.warning(f"Stochastic calculation error: {e}")
            return {'k': 50.0, 'd': 50.0}
    
    def calculate_adx(self, df):
        """Calculate Average Directional Index with NaN handling."""
        try:
            adx = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'])
            return safe_float(adx.adx().iloc[-1], 25.0)
        except Exception as e:
            logger.warning(f"ADX calculation error: {e}")
            return 25.0
    
    def calculate_obv(self, df):
        """Calculate On Balance Volume with NaN handling."""
        try:
            obv = ta.volume.OnBalanceVolumeIndicator(df['Close'], df['Volume'])
            current_obv = safe_float(obv.on_balance_volume().iloc[-1])
            obv_series = obv.on_balance_volume()
            
            if len(obv_series) >= 5:
                prev_obv = safe_float(obv_series.iloc[-5])
                if prev_obv != 0:
                    obv_trend = (safe_float(obv_series.iloc[-1]) - prev_obv) / abs(prev_obv) * 100
                else:
                    obv_trend = 0.0
            else:
                obv_trend = 0.0
                
            return {'current': current_obv, 'trend': safe_float(obv_trend)}
        except Exception as e:
            logger.warning(f"OBV calculation error: {e}")
            return {'current': 0.0, 'trend': 0.0}
    
    def calculate_williams_r(self, df):
        """Calculate Williams %R with NaN handling."""
        try:
            wr = ta.momentum.WilliamsRIndicator(df['High'], df['Low'], df['Close'])
            return safe_float(wr.williams_r().iloc[-1], -50.0)
        except Exception as e:
            logger.warning(f"Williams %R calculation error: {e}")
            return -50.0
    
    def calculate_cci(self, df):
        """Calculate Commodity Channel Index with NaN handling."""
        try:
            cci = ta.trend.CCIIndicator(df['High'], df['Low'], df['Close'])
            return safe_float(cci.cci().iloc[-1], 0.0)
        except Exception as e:
            logger.warning(f"CCI calculation error: {e}")
            return 0.0
    
    def calculate_atr(self, df, period=14):
        """Calculate Average True Range with NaN handling."""
        try:
            atr = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=period)
            return safe_float(atr.average_true_range().iloc[-1])
        except Exception as e:
            logger.warning(f"ATR calculation error: {e}")
            # Fallback: simple range calculation
            try:
                high = safe_float(df['High'].iloc[-1])
                low = safe_float(df['Low'].iloc[-1])
                return high - low if high > low else safe_float(df['Close'].iloc[-1]) * 0.02
            except:
                return 0.0
    
    def calculate_supertrend(self, df, period=10, multiplier=3):
        """Calculate SuperTrend indicator - very popular in Indian markets."""
        try:
            # Calculate ATR
            atr = self.calculate_atr(df, period)
            if atr == 0:
                atr = safe_float(df['Close'].iloc[-1]) * 0.02
            
            hl2 = (df['High'] + df['Low']) / 2
            
            # Basic Upper and Lower Bands
            basic_ub = hl2 + (multiplier * atr)
            basic_lb = hl2 - (multiplier * atr)
            
            # Final Upper and Lower Bands
            final_ub = basic_ub.copy()
            final_lb = basic_lb.copy()
            
            close = df['Close']
            
            # Calculate SuperTrend
            supertrend = pd.Series(index=df.index, dtype=float)
            direction = pd.Series(index=df.index, dtype=int)
            
            for i in range(1, len(df)):
                # Upper Band
                if basic_ub.iloc[i] < final_ub.iloc[i-1] or close.iloc[i-1] > final_ub.iloc[i-1]:
                    final_ub.iloc[i] = basic_ub.iloc[i]
                else:
                    final_ub.iloc[i] = final_ub.iloc[i-1]
                
                # Lower Band
                if basic_lb.iloc[i] > final_lb.iloc[i-1] or close.iloc[i-1] < final_lb.iloc[i-1]:
                    final_lb.iloc[i] = basic_lb.iloc[i]
                else:
                    final_lb.iloc[i] = final_lb.iloc[i-1]
                
                # SuperTrend
                if supertrend.iloc[i-1] == final_ub.iloc[i-1]:
                    if close.iloc[i] <= final_ub.iloc[i]:
                        supertrend.iloc[i] = final_ub.iloc[i]
                        direction.iloc[i] = -1  # Down trend
                    else:
                        supertrend.iloc[i] = final_lb.iloc[i]
                        direction.iloc[i] = 1  # Up trend
                else:
                    if close.iloc[i] >= final_lb.iloc[i]:
                        supertrend.iloc[i] = final_lb.iloc[i]
                        direction.iloc[i] = 1  # Up trend
                    else:
                        supertrend.iloc[i] = final_ub.iloc[i]
                        direction.iloc[i] = -1  # Down trend
            
            current_st = safe_float(supertrend.iloc[-1])
            current_dir = int(direction.iloc[-1]) if not pd.isna(direction.iloc[-1]) else 0
            current_price = safe_float(close.iloc[-1])
            
            return {
                'value': current_st,
                'direction': 'BULLISH' if current_dir == 1 else 'BEARISH',
                'signal': 'BUY' if current_price > current_st else 'SELL'
            }
        except Exception as e:
            logger.warning(f"SuperTrend calculation error: {e}")
            price = safe_float(df['Close'].iloc[-1])
            return {
                'value': price,
                'direction': 'NEUTRAL',
                'signal': 'HOLD'
            }
    
    def calculate_vwap(self, df):
        """Calculate Volume Weighted Average Price."""
        try:
            # VWAP = Cumulative(Price * Volume) / Cumulative(Volume)
            typical_price = (df['High'] + df['Low'] + df['Close']) / 3
            cumulative_tp_vol = (typical_price * df['Volume']).rolling(window=20).sum()
            cumulative_vol = df['Volume'].rolling(window=20).sum()
            
            vwap = cumulative_tp_vol / cumulative_vol
            current_vwap = safe_float(vwap.iloc[-1])
            current_price = safe_float(df['Close'].iloc[-1])
            
            if current_vwap == 0:
                current_vwap = current_price
            
            # Determine position relative to VWAP
            if current_price > current_vwap * 1.02:
                position = 'ABOVE'
                signal = 'BULLISH'
            elif current_price < current_vwap * 0.98:
                position = 'BELOW'
                signal = 'BEARISH'
            else:
                position = 'AT_VWAP'
                signal = 'NEUTRAL'
            
            return {
                'value': current_vwap,
                'position': position,
                'signal': signal,
                'deviation': ((current_price - current_vwap) / current_vwap * 100) if current_vwap > 0 else 0
            }
        except Exception as e:
            logger.warning(f"VWAP calculation error: {e}")
            price = safe_float(df['Close'].iloc[-1])
            return {
                'value': price,
                'position': 'AT_VWAP',
                'signal': 'NEUTRAL',
                'deviation': 0
            }
    
    def calculate_all_indicators(self, df):
        """Calculate all technical indicators with validation."""
        if df is None or df.empty:
            raise ValueError("Empty dataframe provided")
        
        # Ensure minimum data points
        min_required = 50
        if len(df) < min_required:
            logger.warning(f"Only {len(df)} data points, minimum {min_required} recommended")
        
        indicators = {
            'rsi': self.calculate_rsi(df),
            'macd': self.calculate_macd(df),
            'moving_averages': self.calculate_moving_averages(df),
            'bollinger': self.calculate_bollinger_bands(df),
            'stochastic': self.calculate_stochastic(df),
            'adx': self.calculate_adx(df),
            'obv': self.calculate_obv(df),
            'williams_r': self.calculate_williams_r(df),
            'cci': self.calculate_cci(df),
            'atr': self.calculate_atr(df),
            'supertrend': self.calculate_supertrend(df),
            'vwap': self.calculate_vwap(df),
            'current_price': safe_float(df['Close'].iloc[-1]),
            'prev_close': safe_float(df['Close'].iloc[-2]) if len(df) > 1 else safe_float(df['Close'].iloc[-1])
        }
        
        # Validate all values
        for key in ['rsi', 'adx', 'williams_r', 'cci', 'atr']:
            if not is_valid_number(indicators[key]):
                logger.warning(f"Invalid value for {key}, using default")
                indicators[key] = {'rsi': 50.0, 'adx': 25.0, 'williams_r': -50.0, 'cci': 0.0, 'atr': 0.0}.get(key, 0.0)
        
        return indicators


class StockScorer:
    """Score stocks based on technical indicators (0-100)."""
    
    def __init__(self):
        self.weights = {
            'rsi': 12,
            'macd': 12,
            'moving_averages': 15,
            'bollinger': 8,
            'stochastic': 8,
            'adx': 8,
            'volume': 8,
            'momentum': 8,
            'supertrend': 11,
            'vwap': 10
        }
    
    def score_rsi(self, rsi):
        """Score RSI: Oversold (<30) is bullish, Overbought (>70) is bearish."""
        rsi = safe_float(rsi, 50.0)
        
        if rsi < 20:
            return 90
        elif rsi < 30:
            return 75
        elif rsi < 40:
            return 60
        elif rsi < 50:
            return 50
        elif rsi < 60:
            return 45
        elif rsi < 70:
            return 35
        elif rsi < 80:
            return 20
        else:
            return 10
    
    def score_macd(self, macd_data):
        """Score MACD based on histogram and crossover."""
        try:
            hist = safe_float(macd_data['histogram'])
            macd_val = safe_float(macd_data['macd'])
            signal_val = safe_float(macd_data['signal'])
        except:
            return 50
        
        score = 50
        if hist > 0:
            score += 25
        else:
            score -= 25
        
        if macd_val > signal_val:
            score += 15
        else:
            score -= 15
        
        return max(0, min(100, score))
    
    def score_moving_averages(self, current_price, ma_data):
        """Score based on price position relative to moving averages."""
        score = 50
        
        for ma_name, ma_value in ma_data.items():
            ma_val = safe_float(ma_value)
            if ma_val > 0:
                if current_price > ma_val:
                    score += 10
                else:
                    score -= 10
        
        # Golden/Death cross detection
        sma50 = safe_float(ma_data.get('sma_50', 0))
        sma200 = safe_float(ma_data.get('sma_200', 0))
        if sma50 > 0 and sma200 > 0:
            if sma50 > sma200:
                score += 10  # Golden cross
            else:
                score -= 10  # Death cross
        
        return max(0, min(100, score))
    
    def score_bollinger(self, current_price, bb_data):
        """Score based on Bollinger Band position."""
        upper = safe_float(bb_data['upper'])
        lower = safe_float(bb_data['lower'])
        
        if upper == 0 or lower == 0:
            return 50
        
        band_width = upper - lower
        if band_width == 0:
            return 50
        
        position = (current_price - lower) / band_width
        
        if position < 0.1:
            return 80  # Near lower band - potential bounce
        elif position < 0.3:
            return 65
        elif position < 0.5:
            return 50
        elif position < 0.7:
            return 40
        elif position < 0.9:
            return 30
        else:
            return 15  # Near upper band - potential reversal
    
    def score_stochastic(self, stoch_data):
        """Score Stochastic Oscillator."""
        k = safe_float(stoch_data['k'], 50.0)
        d = safe_float(stoch_data['d'], 50.0)
        
        score = 50
        if k < 20:
            score += 30
        elif k < 30:
            score += 15
        elif k > 80:
            score -= 30
        elif k > 70:
            score -= 15
        
        if k > d:
            score += 10
        else:
            score -= 10
        
        return max(0, min(100, score))
    
    def score_adx(self, adx):
        """Score ADX - measures trend strength."""
        adx = safe_float(adx, 25.0)
        
        if adx > 50:
            return 80  # Very strong trend
        elif adx > 40:
            return 70
        elif adx > 30:
            return 60
        elif adx > 20:
            return 50
        else:
            return 30  # Weak trend
    
    def score_volume(self, obv_data):
        """Score based on OBV trend."""
        trend = safe_float(obv_data.get('trend', 0))
        
        if trend > 10:
            return 80
        elif trend > 5:
            return 65
        elif trend > 0:
            return 55
        elif trend > -5:
            return 45
        elif trend > -10:
            return 35
        else:
            return 20
    
    def score_momentum(self, williams_r, cci):
        """Score based on Williams %R and CCI."""
        score = 50
        
        wr = safe_float(williams_r, -50.0)
        if wr < -80:
            score += 20  # Oversold
        elif wr > -20:
            score -= 20  # Overbought
        
        cci_val = safe_float(cci, 0.0)
        if cci_val < -100:
            score += 15  # Oversold
        elif cci_val > 100:
            score -= 15  # Overbought
        
        return max(0, min(100, score))
    
    def score_supertrend(self, supertrend_data):
        """Score based on SuperTrend indicator."""
        if not supertrend_data:
            return 50
        
        signal = supertrend_data.get('signal', 'HOLD')
        direction = supertrend_data.get('direction', 'NEUTRAL')
        
        if signal == 'BUY' and direction == 'BULLISH':
            return 85
        elif signal == 'BUY':
            return 70
        elif signal == 'SELL' and direction == 'BEARISH':
            return 15
        elif signal == 'SELL':
            return 30
        else:
            return 50
    
    def score_vwap(self, vwap_data):
        """Score based on VWAP position."""
        if not vwap_data:
            return 50
        
        signal = vwap_data.get('signal', 'NEUTRAL')
        deviation = safe_float(vwap_data.get('deviation', 0))
        
        if signal == 'BULLISH':
            base = 65
            # Bonus for strong deviation
            if deviation > 3:
                base = 75
            return base
        elif signal == 'BEARISH':
            base = 35
            # Penalty for strong deviation
            if deviation < -3:
                base = 25
            return base
        else:
            return 50
    
    def calculate_total_score(self, indicators):
        """Calculate weighted total score with all indicators."""
        scores = {
            'rsi': self.score_rsi(indicators['rsi']),
            'macd': self.score_macd(indicators['macd']),
            'moving_averages': self.score_moving_averages(
                indicators['current_price'], 
                indicators['moving_averages']
            ),
            'bollinger': self.score_bollinger(
                indicators['current_price'], 
                indicators['bollinger']
            ),
            'stochastic': self.score_stochastic(indicators['stochastic']),
            'adx': self.score_adx(indicators['adx']),
            'volume': self.score_volume(indicators['obv']),
            'momentum': self.score_momentum(
                indicators['williams_r'], 
                indicators['cci']
            ),
            'supertrend': self.score_supertrend(indicators.get('supertrend', {})),
            'vwap': self.score_vwap(indicators.get('vwap', {}))
        }
        
        # Calculate weighted average
        total_score = sum(
            scores[key] * self.weights[key] / 100 
            for key in scores
        )
        
        return {
            'total': round(total_score, 1),
            'breakdown': scores,
            'recommendation': self.get_recommendation(total_score)
        }
    
    def get_recommendation(self, score):
        """Convert score to recommendation."""
        if score >= 75:
            return "STRONG BUY"
        elif score >= 60:
            return "BUY"
        elif score >= 45:
            return "HOLD"
        elif score >= 30:
            return "SELL"
        else:
            return "STRONG SELL"


class StopLossCalculator:
    """Calculate stop-loss and target prices."""
    
    @staticmethod
    def calculate_targets(indicators, recommendation):
        """Calculate stop-loss and target prices based on ATR."""
        price = safe_float(indicators.get('current_price', 0))
        atr = safe_float(indicators.get('atr', 0))
        
        # Fallback if ATR is 0
        if atr == 0:
            atr = price * 0.02  # Assume 2% volatility
        
        result = {
            'current_price': round(price, 2),
            'atr': round(atr, 2),
            'stop_loss': None,
            'target1': None,
            'target2': None,
            'target3': None,
            'risk_reward': None,
            'risk_amount': None,
            'reward_amount': None,
            'position': None
        }
        
        if price <= 0:
            return result
        
        if recommendation in ['STRONG BUY', 'BUY']:
            # For buy positions
            stop_loss = price - (atr * 1.5)
            target1 = price + (atr * 1.5)  # Conservative
            target2 = price + (atr * 2.5)  # Moderate
            target3 = price + (atr * 4.0)  # Aggressive
            
            result['stop_loss'] = round(stop_loss, 2)
            result['target1'] = round(target1, 2)
            result['target2'] = round(target2, 2)
            result['target3'] = round(target3, 2)
            result['risk_amount'] = round(price - stop_loss, 2)
            result['reward_amount'] = round(target2 - price, 2)
            result['position'] = 'LONG (Buy)'
            
            if result['risk_amount'] > 0:
                result['risk_reward'] = round(result['reward_amount'] / result['risk_amount'], 2)
            
        elif recommendation in ['SELL', 'STRONG SELL']:
            # For sell/short positions
            stop_loss = price + (atr * 1.5)
            target1 = price - (atr * 1.5)
            target2 = price - (atr * 2.5)
            target3 = price - (atr * 4.0)
            
            result['stop_loss'] = round(stop_loss, 2)
            result['target1'] = round(target1, 2)
            result['target2'] = round(target2, 2)
            result['target3'] = round(target3, 2)
            result['risk_amount'] = round(stop_loss - price, 2)
            result['reward_amount'] = round(price - target2, 2)
            result['position'] = 'SHORT (Sell)'
            
            if result['risk_amount'] > 0:
                result['risk_reward'] = round(result['reward_amount'] / result['risk_amount'], 2)
        
        else:  # HOLD
            # For hold, calculate both upside and downside levels
            resistance = price + (atr * 1.5)
            support = price - (atr * 1.5)
            target_up = price + (atr * 2.5)
            target_down = price - (atr * 2.5)
            
            result['stop_loss'] = round(support, 2)  # Downside support
            result['target1'] = round(resistance, 2)  # Upside resistance
            result['target2'] = round(target_up, 2)  # Upside target
            result['target3'] = round(target_down, 2)  # Downside target
            result['risk_amount'] = round(price - support, 2)
            result['reward_amount'] = round(resistance - price, 2)
            result['position'] = 'HOLD (Neutral)'
            
            if result['risk_amount'] > 0:
                result['risk_reward'] = round(result['reward_amount'] / result['risk_amount'], 2)
        
        return result


class StockScannerApp:
    """Main GUI Application for Stock Scanner."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Indian Stock Technical Scanner & Recommender v2.0")
        self.root.geometry("1400x900")
        self.root.configure(bg='#1a1a2e')
        
        # Make window resizable
        self.root.minsize(1200, 800)
        
        # Initialize components
        self.analyzer = TechnicalAnalyzer()
        self.scorer = StockScorer()
        self.target_calculator = StopLossCalculator()
        self.gui_manager = ThreadSafeGUI(root)
        self.watchlist = []
        self.results = []
        self.is_scanning = False
        
        # Load saved watchlist
        self.watchlist_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.json")
        self.load_watchlist()
        
        # Setup GUI
        self.setup_styles()
        self.create_widgets()
        self.update_watchlist_display()
        
        # Center window
        self.center_window()
        
        logger.info("Application started")
    
    def center_window(self):
        """Center the window on screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        
        # Try to use a theme that works
        available_themes = style.theme_names()
        if 'clam' in available_themes:
            style.theme_use('clam')
        elif 'vista' in available_themes:
            style.theme_use('vista')
        elif 'winnative' in available_themes:
            style.theme_use('winnative')
        
        # Configure colors
        style.configure('Title.TLabel', 
                       background='#1a1a2e', 
                       foreground='#00d4ff',
                       font=('Helvetica', 20, 'bold'))
        
        style.configure('Header.TLabel',
                       background='#1a1a2e',
                       foreground='#ffffff',
                       font=('Helvetica', 11, 'bold'))
        
        style.configure('Treeview',
                       background='#16213e',
                       foreground='#ffffff',
                       fieldbackground='#16213e',
                       font=('Helvetica', 10))
        
        style.configure('Treeview.Heading',
                       background='#0f3460',
                       foreground='#00d4ff',
                       font=('Helvetica', 10, 'bold'))
        
        style.map('Treeview',
                  background=[('selected', '#e74c3c')],
                  foreground=[('selected', 'white')])
    
    def create_widgets(self):
        """Create all GUI widgets."""
        # Main container
        main_frame = tk.Frame(self.root, bg='#1a1a2e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, 
                               text="Indian Stock Technical Scanner v2.0",
                               style='Title.TLabel')
        title_label.pack(pady=(0, 5))
        
        subtitle_label = ttk.Label(main_frame,
                                  text="With SuperTrend, VWAP, Stop-Loss Calculator & Smart Caching",
                                  background='#1a1a2e',
                                  foreground='#8892b0',
                                  font=('Helvetica', 10))
        subtitle_label.pack(pady=(0, 10))
        
        # Top control panel
        control_frame = tk.Frame(main_frame, bg='#16213e', relief=tk.RIDGE, bd=2)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Watchlist management section
        wl_frame = tk.LabelFrame(control_frame, text="Watchlist Management",
                                bg='#16213e', fg='#00d4ff',
                                font=('Helvetica', 11, 'bold'))
        wl_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Stock entry
        entry_frame = tk.Frame(wl_frame, bg='#16213e')
        entry_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(entry_frame, text="Stock Symbol:", bg='#16213e', fg='white',
                font=('Helvetica', 10)).pack(side=tk.LEFT, padx=5)
        
        self.stock_entry = tk.Entry(entry_frame, font=('Helvetica', 11),
                                   bg='#0f3460', fg='white', insertbackground='white',
                                   width=15)
        self.stock_entry.pack(side=tk.LEFT, padx=5)
        self.stock_entry.bind('<Return>', lambda e: self.add_stock())
        
        # Buttons
        btn_frame = tk.Frame(wl_frame, bg='#16213e')
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        btn_style = {'font': ('Helvetica', 9, 'bold'), 'relief': tk.RAISED, 'bd': 1, 'cursor': 'hand2'}
        
        self.add_btn = tk.Button(btn_frame, text="Add Stock",
                                bg='#00b894', fg='white',
                                command=self.add_stock, **btn_style)
        self.add_btn.pack(side=tk.LEFT, padx=3)
        
        self.del_btn = tk.Button(btn_frame, text="Delete Stock",
                                bg='#e74c3c', fg='white',
                                command=self.delete_stock, **btn_style)
        self.del_btn.pack(side=tk.LEFT, padx=3)
        
        self.clear_btn = tk.Button(btn_frame, text="Clear All",
                                  bg='#e67e22', fg='white',
                                  command=self.clear_watchlist, **btn_style)
        self.clear_btn.pack(side=tk.LEFT, padx=3)
        
        # Import/Export section
        io_frame = tk.LabelFrame(control_frame, text="Import / Export",
                                bg='#16213e', fg='#00d4ff',
                                font=('Helvetica', 11, 'bold'))
        io_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        io_btn_frame = tk.Frame(io_frame, bg='#16213e')
        io_btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.import_btn = tk.Button(io_btn_frame, text="Import List",
                                   bg='#6c5ce7', fg='white',
                                   command=self.import_watchlist, **btn_style)
        self.import_btn.pack(side=tk.LEFT, padx=3)
        
        # Add Fix PDF button (shows only if pdfplumber not available)
        if not PDFPLUMBER_AVAILABLE:
            self.fix_pdf_btn = tk.Button(io_btn_frame, text="Fix PDF Support",
                                        bg='#e74c3c', fg='white',
                                        command=self.install_pdfplumber, **btn_style)
            self.fix_pdf_btn.pack(side=tk.LEFT, padx=3)
        
        self.export_btn = tk.Button(io_btn_frame, text="Export Watchlist",
                                   bg='#0984e3', fg='white',
                                   command=self.export_watchlist, **btn_style)
        self.export_btn.pack(side=tk.LEFT, padx=3)
        
        self.export_results_btn = tk.Button(io_btn_frame, text="Export Results",
                                           bg='#00cec9', fg='white',
                                           command=self.export_results, **btn_style)
        self.export_results_btn.pack(side=tk.LEFT, padx=3)
        
        # Scan controls
        scan_frame = tk.LabelFrame(control_frame, text="Scan Controls",
                                  bg='#16213e', fg='#00d4ff',
                                  font=('Helvetica', 11, 'bold'))
        scan_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scan_btn_frame = tk.Frame(scan_frame, bg='#16213e')
        scan_btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.scan_btn = tk.Button(scan_btn_frame, text="Scan All Stocks",
                                 bg='#e74c3c', fg='white', width=15,
                                 font=('Helvetica', 11, 'bold'),
                                 command=self.start_scan, cursor='hand2')
        self.scan_btn.pack(side=tk.LEFT, padx=5)
        
        self.clear_cache_btn = tk.Button(scan_btn_frame, text="Clear Cache",
                                        bg='#636e72', fg='white',
                                        command=self.clear_cache, **btn_style)
        self.clear_cache_btn.pack(side=tk.LEFT, padx=5)
        
        self.progress = ttk.Progressbar(scan_btn_frame, mode='determinate', length=150)
        self.progress.pack(side=tk.LEFT, padx=10)
        
        self.status_label = tk.Label(scan_btn_frame, text="Ready",
                                    bg='#16213e', fg='#00d4ff',
                                    font=('Helvetica', 10))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Main content area with notebook
        notebook_frame = tk.Frame(main_frame, bg='#1a1a2e')
        notebook_frame.pack(fill=tk.BOTH, expand=True)
        
        self.notebook = ttk.Notebook(notebook_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Watchlist
        self.create_watchlist_tab()
        
        # Tab 2: Scan Results
        self.create_results_tab()
        
        # Tab 3: Score Breakdown
        self.create_breakdown_tab()
        
        # Tab 4: Stop-Loss & Targets
        self.create_targets_tab()
        
        # Bottom info bar
        info_frame = tk.Frame(main_frame, bg='#0f3460', relief=tk.SUNKEN, bd=1)
        info_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.info_label = tk.Label(info_frame,
                                   text="Enter stock symbols (e.g., RELIANCE, TCS, INFY) and click Scan | F5 to scan | Ctrl+I to import",
                                   bg='#0f3460', fg='#8892b0',
                                   font=('Helvetica', 9),
                                   anchor=tk.W)
        self.info_label.pack(fill=tk.X, padx=10, pady=3)
        
        # Bind keyboard shortcuts
        self.bind_shortcuts()
    
    def bind_shortcuts(self):
        """Bind keyboard shortcuts."""
        self.root.bind('<F5>', lambda e: self.start_scan())
        self.root.bind('<Control-i>', lambda e: self.import_watchlist())
        self.root.bind('<Control-e>', lambda e: self.export_results())
        self.root.bind('<Control-n>', lambda e: self.stock_entry.focus())
        self.root.bind('<Delete>', lambda e: self.delete_stock())
    
    def create_watchlist_tab(self):
        """Create watchlist tab."""
        tab = tk.Frame(self.notebook, bg='#16213e')
        self.notebook.add(tab, text="Watchlist")
        
        list_frame = tk.Frame(tab, bg='#16213e')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.watchlist_listbox = tk.Listbox(list_frame,
                                           bg='#0f3460',
                                           fg='#00d4ff',
                                           font=('Consolas', 12),
                                           selectbackground='#e74c3c',
                                           selectforeground='white',
                                           yscrollcommand=scrollbar.set)
        self.watchlist_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.watchlist_listbox.yview)
        
        self.count_label = tk.Label(tab, text="Stocks in watchlist: 0",
                                   bg='#16213e', fg='#8892b0',
                                   font=('Helvetica', 10))
        self.count_label.pack(pady=5)
    
    def create_results_tab(self):
        """Create scan results tab."""
        tab = tk.Frame(self.notebook, bg='#16213e')
        self.notebook.add(tab, text="Scan Results")
        
        columns = ('Symbol', 'Price', 'Change%', 'RSI', 'SuperTrend', 'VWAP', 'Score', 'Recommendation')
        
        tree_frame = tk.Frame(tab, bg='#16213e')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar_y = tk.Scrollbar(tree_frame)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        scrollbar_x = tk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.results_tree = ttk.Treeview(tree_frame, columns=columns,
                                        show='headings',
                                        yscrollcommand=scrollbar_y.set,
                                        xscrollcommand=scrollbar_x.set)
        
        col_widths = {'Symbol': 100, 'Price': 90, 'Change%': 80,
                     'RSI': 70, 'SuperTrend': 90, 'VWAP': 80, 'Score': 80, 'Recommendation': 130}
        
        for col in columns:
            self.results_tree.heading(col, text=col, anchor=tk.CENTER)
            self.results_tree.column(col, width=col_widths.get(col, 100),
                                    anchor=tk.CENTER)
        
        self.results_tree.pack(fill=tk.BOTH, expand=True)
        scrollbar_y.config(command=self.results_tree.yview)
        scrollbar_x.config(command=self.results_tree.xview)
        
        self.results_tree.bind('<Double-1>', self.show_breakdown)
    
    def create_breakdown_tab(self):
        """Create score breakdown tab."""
        tab = tk.Frame(self.notebook, bg='#16213e')
        self.notebook.add(tab, text="Score Breakdown")
        
        title = tk.Label(tab, text="Double-click a stock from Scan Results to view breakdown",
                        bg='#16213e', fg='#00d4ff',
                        font=('Helvetica', 14, 'bold'))
        title.pack(pady=20)
        
        self.breakdown_frame = tk.Frame(tab, bg='#16213e')
        self.breakdown_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    def create_targets_tab(self):
        """Create stop-loss and targets tab."""
        tab = tk.Frame(self.notebook, bg='#16213e')
        self.notebook.add(tab, text="Stop-Loss & Targets")
        
        # Create canvas with scrollbar
        self.targets_canvas = tk.Canvas(tab, bg='#16213e', highlightthickness=0)
        self.targets_scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self.targets_canvas.yview)
        
        self.targets_frame = tk.Frame(self.targets_canvas, bg='#16213e')
        
        self.targets_frame.bind("<Configure>", 
            lambda e: self.targets_canvas.configure(scrollregion=self.targets_canvas.bbox("all")))
        
        self.targets_canvas.create_window((0, 0), window=self.targets_frame, anchor="nw")
        self.targets_canvas.configure(yscrollcommand=self.targets_scrollbar.set)
        
        self.targets_scrollbar.pack(side="right", fill="y")
        self.targets_canvas.pack(side="left", fill="both", expand=True)
        
        # Bind mousewheel
        def _on_mousewheel(event):
            self.targets_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.targets_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Initial message
        tk.Label(self.targets_frame, 
                text="Double-click a stock from Scan Results to view targets",
                bg='#16213e', fg='#00d4ff',
                font=('Helvetica', 14, 'bold')).pack(pady=50)
    
    def add_stock(self):
        """Add stock to watchlist."""
        symbol = self.stock_entry.get().strip().upper()
        
        if not symbol:
            messagebox.showwarning("Warning", "Please enter a stock symbol!")
            return
        
        # Clean symbol
        symbol = re.sub(r'[^A-Z0-9&-]', '', symbol)
        
        if not symbol:
            messagebox.showwarning("Warning", "Invalid stock symbol!")
            return
        
        if symbol in self.watchlist:
            messagebox.showinfo("Info", f"{symbol} is already in watchlist!")
            return
        
        self.watchlist.append(symbol)
        self.stock_entry.delete(0, tk.END)
        self.update_watchlist_display()
        self.save_watchlist()
        self.info_label.config(text=f"Added {symbol} to watchlist")
        logger.info(f"Added {symbol} to watchlist")
    
    def delete_stock(self):
        """Delete selected stock from watchlist."""
        selection = self.watchlist_listbox.curselection()
        
        if not selection:
            messagebox.showwarning("Warning", "Please select a stock to delete!")
            return
        
        symbol = self.watchlist_listbox.get(selection[0])
        self.watchlist.remove(symbol)
        self.update_watchlist_display()
        self.save_watchlist()
        self.info_label.config(text=f"Removed {symbol} from watchlist")
        logger.info(f"Removed {symbol} from watchlist")
    
    def clear_watchlist(self):
        """Clear entire watchlist."""
        if messagebox.askyesno("Confirm", "Clear entire watchlist?"):
            self.watchlist.clear()
            self.update_watchlist_display()
            self.save_watchlist()
            self.info_label.config(text="Watchlist cleared")
            logger.info("Watchlist cleared")
    
    def clear_cache(self):
        """Clear data cache."""
        self.analyzer.cache.clear()
        self.info_label.config(text="Cache cleared")
        messagebox.showinfo("Cache Cleared", "Data cache has been cleared.\nNext scan will fetch fresh data.")
        logger.info("Cache cleared by user")
    
    def install_pdfplumber(self):
        """Install pdfplumber package."""
        global pdfplumber, PDFPLUMBER_AVAILABLE
        
        result = messagebox.askyesno(
            "Install PDF Support",
            "This will install the 'pdfplumber' package to enable PDF import.\n\n"
            "Do you want to continue?"
        )
        
        if not result:
            return
        
        try:
            import subprocess
            self.info_label.config(text="Installing pdfplumber... Please wait...")
            self.root.update()
            
            # Run pip install
            process = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "pdfplumber"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                # Try to import
                try:
                    import pdfplumber
                    PDFPLUMBER_AVAILABLE = True
                    
                    # Remove the Fix PDF button if it exists
                    if hasattr(self, 'fix_pdf_btn'):
                        self.fix_pdf_btn.destroy()
                    
                    messagebox.showinfo(
                        "Success!",
                        "pdfplumber installed successfully!\n\n"
                        "PDF import is now enabled.\n"
                        "You can now import PDF files with stock symbols."
                    )
                    self.info_label.config(text="PDF support enabled! You can now import PDF files.")
                    logger.info("pdfplumber installed successfully")
                except ImportError as e:
                    messagebox.showerror(
                        "Import Error",
                        f"pdfplumber was installed but cannot be imported.\n\n"
                        f"Error: {e}\n\n"
                        f"Please restart the application."
                    )
            else:
                messagebox.showerror(
                    "Installation Failed",
                    f"Failed to install pdfplumber.\n\n"
                    f"Error:\n{stderr}\n\n"
                    f"Please install manually:\n"
                    f"1. Open Command Prompt/Terminal\n"
                    f"2. Run: pip install pdfplumber\n"
                    f"3. Restart this application"
                )
                logger.error(f"pdfplumber install failed: {stderr}")
                
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"An error occurred: {e}\n\n"
                f"Please install manually:\n"
                f"  pip install pdfplumber"
            )
            logger.error(f"install_pdfplumber error: {e}")
    
    def update_watchlist_display(self):
        """Update watchlist listbox."""
        self.watchlist_listbox.delete(0, tk.END)
        for stock in sorted(self.watchlist):
            self.watchlist_listbox.insert(tk.END, stock)
        self.count_label.config(text=f"Stocks in watchlist: {len(self.watchlist)}")
    
    def save_watchlist(self):
        """Save watchlist to file."""
        try:
            with open(self.watchlist_file, 'w') as f:
                json.dump(self.watchlist, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving watchlist: {e}")
    
    def load_watchlist(self):
        """Load watchlist from file."""
        try:
            if os.path.exists(self.watchlist_file):
                with open(self.watchlist_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.watchlist = data
                    else:
                        self.watchlist = []
        except Exception as e:
            logger.error(f"Error loading watchlist: {e}")
            self.watchlist = []
    
    def import_watchlist(self):
        """Import watchlist from file (supports JSON, CSV, TXT, Excel, and PDF)."""
        filetypes = [
            ("All Supported", "*.xlsx *.xls *.pdf *.json *.csv *.txt"),
            ("Excel files", "*.xlsx *.xls"),
            ("PDF files", "*.pdf"),
            ("JSON files", "*.json"),
            ("CSV files", "*.csv"),
            ("Text files", "*.txt"),
            ("All files", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(
            title="Import Watchlist",
            filetypes=filetypes
        )
        
        if not filepath:
            return
        
        try:
            imported = []
            filename = os.path.basename(filepath)
            file_ext = os.path.splitext(filepath)[1].lower()
            
            # Show processing message for PDFs
            if file_ext == '.pdf':
                self.info_label.config(text=f"Processing PDF file: {filename}...")
                self.root.update()
            
            # Excel files
            if file_ext in ('.xlsx', '.xls'):
                imported = self.parse_excel_file(filepath)
            
            # PDF files
            elif file_ext == '.pdf':
                if not PDFPLUMBER_AVAILABLE:
                    # Show detailed error with install option
                    result = messagebox.askyesno(
                        "PDF Support Required",
                        "PDF import requires the 'pdfplumber' package.\n\n"
                        "Would you like to install it now?\n\n"
                        "Click 'Yes' to install automatically,\n"
                        "or 'No' to cancel and install manually later."
                    )
                    
                    if result:
                        # Try to install
                        try:
                            import subprocess
                            self.info_label.config(text="Installing pdfplumber...")
                            self.root.update()
                            
                            process = subprocess.Popen(
                                [sys.executable, "-m", "pip", "install", "pdfplumber"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            stdout, stderr = process.communicate()
                            
                            if process.returncode == 0:
                                # Try importing again
                                try:
                                    import pdfplumber as _pdf
                                    globals()['pdfplumber'] = _pdf
                                    globals()['PDFPLUMBER_AVAILABLE'] = True
                                    messagebox.showinfo("Success", "pdfplumber installed successfully!\nPlease try importing again.")
                                    self.info_label.config(text="pdfplumber installed. Try importing again.")
                                    return
                                except ImportError:
                                    messagebox.showinfo("Restart Required", "pdfplumber installed. Please restart the application.")
                                    return
                            else:
                                messagebox.showerror("Install Failed", f"Could not install pdfplumber.\n\n{stderr}")
                                return
                        except Exception as install_err:
                            messagebox.showerror(
                                "Installation Failed",
                                f"Could not install pdfplumber automatically.\n\n"
                                f"Error: {install_err}\n\n"
                                f"Please install manually by running:\n"
                                f"  {sys.executable} -m pip install pdfplumber"
                            )
                            return
                    else:
                        return
                
                imported = self.parse_pdf_file(filepath)
                
                # Log what was found
                logger.info(f"PDF parsing found {len(imported)} symbols: {imported[:20]}...")
            
            # JSON files
            elif file_ext == '.json':
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        imported = [str(s).strip().upper() for s in data if str(s).strip()]
                    elif isinstance(data, dict):
                        for key in ['watchlist', 'stocks', 'symbols']:
                            if key in data:
                                imported = [str(s).strip().upper() for s in data[key] if str(s).strip()]
                                break
            
            # CSV files
            elif file_ext == '.csv':
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if row and row[0].strip():
                            val = row[0].strip().upper()
                            if val and len(val) >= 2:
                                imported.append(val)
            
            # Text files
            elif file_ext == '.txt':
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    for line in f:
                        symbol = line.strip().upper()
                        if symbol and len(symbol) >= 2:
                            imported.append(symbol)
            
            else:
                messagebox.showwarning("Warning", f"Unsupported file format: {file_ext}")
                return
            
            # Remove duplicates while preserving order
            seen = set()
            unique_imported = []
            for s in imported:
                if s not in seen:
                    seen.add(s)
                    unique_imported.append(s)
            
            # Validate and filter symbols
            valid_symbols = [s for s in unique_imported if self.is_valid_symbol(s)]
            
            # Add to watchlist (avoid duplicates)
            added = 0
            for symbol in valid_symbols:
                if symbol not in self.watchlist:
                    self.watchlist.append(symbol)
                    added += 1
            
            self.update_watchlist_display()
            self.save_watchlist()
            
            # Show detailed result
            if file_ext == '.pdf':
                result_msg = (
                    f"PDF Import Results for {filename}:\n\n"
                    f"• Total text extracted from PDF\n"
                    f"• Symbols found: {len(unique_imported)}\n"
                    f"• Valid symbols: {len(valid_symbols)}\n"
                    f"• New stocks added: {added}\n"
                    f"• Already in watchlist: {len(valid_symbols) - added}\n\n"
                )
                
                if valid_symbols:
                    # Show first 20 symbols found
                    sample = valid_symbols[:20]
                    result_msg += f"Stocks found:\n{', '.join(sample)}"
                    if len(valid_symbols) > 20:
                        result_msg += f"\n... and {len(valid_symbols) - 20} more"
                
                if added > 0:
                    messagebox.showinfo("PDF Import Success", result_msg)
                else:
                    messagebox.showinfo("PDF Import Info", result_msg)
            else:
                if added > 0:
                    messagebox.showinfo("Import Success", 
                                      f"Imported {added} new stocks from {filename}!\n"
                                      f"Total symbols found: {len(unique_imported)}\n"
                                      f"Valid symbols added: {added}")
                else:
                    messagebox.showinfo("Import Info", 
                                      f"No new stocks to import from {filename}.\n"
                                      f"Total symbols found: {len(unique_imported)}\n"
                                      f"Already in watchlist or invalid.")
            
            self.info_label.config(text=f"Imported {added} stocks from {filename}")
            logger.info(f"Imported {added} stocks from {filename}")
            
        except Exception as e:
            error_msg = f"Failed to import: {str(e)}"
            messagebox.showerror("Import Error", error_msg)
            logger.error(f"Import error: {e}")
            
            # Additional help for PDF errors
            if file_ext == '.pdf':
                messagebox.showinfo("PDF Import Tips", 
                    "If PDF import fails, try these alternatives:\n\n"
                    "1. Convert PDF to Excel/CSV first\n"
                    "2. Copy stock symbols from PDF\n"
                    "3. Use 'Add Stock' to add manually\n"
                    "4. Create a .txt file with symbols")
    
    def parse_excel_file(self, filepath):
        """Parse Excel file and extract stock symbols."""
        symbols = []
        
        try:
            df = pd.read_excel(filepath, header=None)
            
            for col in df.columns:
                for value in df[col].dropna():
                    val_str = str(value).strip().upper()
                    if val_str and len(val_str) >= 2 and val_str.replace('-', '').replace('&', '').isalpha():
                        symbols.append(val_str)
        except Exception as e:
            try:
                wb = load_workbook(filepath, data_only=True)
                for sheet in wb.sheetnames:
                    ws = wb[sheet]
                    for row in ws.iter_rows():
                        for cell in row:
                            if cell.value:
                                val_str = str(cell.value).strip().upper()
                                if val_str and len(val_str) >= 2 and val_str.replace('-', '').replace('&', '').isalpha():
                                    symbols.append(val_str)
            except Exception as e2:
                raise Exception(f"Failed to parse Excel file: {str(e2)}")
        
        return symbols
    
    def parse_pdf_file(self, filepath):
        """Parse PDF file and extract stock symbols with improved detection."""
        symbols = []
        
        # Comprehensive list of known NSE/BSE stock symbols
        known_symbols = {
            # Nifty 50
            'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN',
            'WIPRO', 'TATAMOTORS', 'TATASTEEL', 'ADANIENT', 'ADANIPORTS',
            'BHARTIARTL', 'HINDUNILVR', 'ITC', 'KOTAKBANK', 'LT', 'MARUTI',
            'ONGC', 'POWERGRID', 'SUNPHARMA', 'AXISBANK', 'BAJFINANCE',
            'BAJAJFINSV', 'BAJAJ-AUTO', 'BPCL', 'CIPLA', 'COALINDIA',
            'DIVISLAB', 'DRREDDY', 'EICHERMOT', 'GRASIM', 'HCLTECH',
            'HEROMOTOCO', 'HINDALCO', 'HINDPETRO', 'INDUSINDBK', 'JSWSTEEL',
            'NTPC', 'NESTLEIND', 'PIDILITIND', 'SBILIFE',
            'SHREECEM', 'TATACONSUM', 'TECHM', 'TITAN', 'ULTRACEMCO',
            'UPL', 'VEDL', 'ZEEL', 'ASIANPAINT', 'APOLLOHOSP',
            'BAJAJHLDNG', 'BRITANNIA', 'CHOLAFIN', 'DABUR', 'GAIL',
            'GODREJCP', 'HAVELLS', 'HDFCLIFE', 'ICICIPRULI', 'INDUSTOWER',
            'JINDALSTEL', 'LICI', 'MARICO', 'MUTHOOTFIN', 'NAUKRI',
            'PIIND', 'SBICARD', 'SIEMENS', 'SRF', 'TATAPOWER',
            'TRENT', 'VOLTAS', 'ZOMATO', 'TATAELXSI', 'PERSISTENT',
            'COFORGE', 'MPHASIS', 'LTIM', 'OFSS', 'SONACOMS',
            # Additional popular stocks
            'ABB', 'ADANIGREEN', 'ADANITRANS', 'AMBUJACEM', 'ATGL',
            'AUBANK', 'BALKRISIND', 'BANDHANBNK', 'BATAINDIA', 'BEL',
            'BERGEPAINT', 'BHEL', 'BIOCON', 'BOSCHLTD', 'CANBK',
            'CHAMBLFERT', 'COLPAL', 'CONCOR', 'COROMANDEL', 'CROMPTON',
            'CUB', 'CUMMINSIND', 'DALBHARAT', 'DEEPAKNTR', 'DELTACORP',
            'DMART', 'ESCORTS', 'FEDERALBNK', 'GLENMARK', 'GMRINFRA',
            'GODREJPROP', 'GSPL', 'HAL', 'HONAUT', 'IDFCFIRSTB',
            'IEX', 'INDHOTEL', 'INDIACEM', 'INDIAMART', 'INDIGO',
            'IRCTC', 'JUBLFOOD', 'JUSTDIAL', 'KAJARIACER', 'KANSAINER',
            'LALPATHLAB', 'LICHSGFIN', 'LUPIN', 'MANAPPURAM', 'MARICO',
            'MFSL', 'MGL', 'MINDTREE', 'MOTHERSON', 'MPHASIS',
            'MUTHOOTFIN', 'NATIONALUM', 'NAVINFLUOR', 'OBEROIRLTY',
            'OLECTRA', 'PAGEIND', 'PEL', 'PERSISTENT', 'PETRONET',
            'PFC', 'PFIZER', 'POLYCAB', 'PRESTIGE', 'PVR',
            'RAIN', 'RAMCOCEM', 'RBLBANK', 'RECLTD', 'SAIL',
            'SBICARD', 'SHRIRAMFIN', 'STAR', 'SUNTV', 'SYNGENE',
            'TATACHEM', 'TATACOMM', 'TATAINVEST', 'TORNTPHARM',
            'TORNTPOWER', 'TRENT', 'TRIDENT', 'TVSMOTOR', 'UBL',
            'UJJIVANSFB', 'UNIONBANK', 'UNITDSPR', 'UPL', 'VEDL',
            'VGUARD', 'VINATIORGA', 'WHIRLPOOL', 'YESBANK', 'ZEEL',
            'ZYDUSLIFE', 'ZYDUSWELL'
        }
        
        # Words to exclude (common English words that look like symbols)
        exclude_words = {
            'THE', 'AND', 'FOR', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS',
            'ONE', 'OUR', 'OUT', 'ARE', 'HAS', 'HIS', 'HOW', 'ITS', 'MAY', 'NEW',
            'NOW', 'OLD', 'SEE', 'WAY', 'WHO', 'BOY', 'DID', 'GET', 'HIM', 'LET',
            'SAY', 'SHE', 'TOO', 'USE', 'DAD', 'MOM', 'SIR', 'DAY', 'HAD', 'HIT',
            'MAN', 'RAN', 'SAT', 'TOP', 'WIN', 'YES', 'YET', 'AGO', 'BAD', 'BIG',
            'END', 'FAR', 'FEW', 'GOT', 'HOT', 'JOB', 'LOT', 'OWN', 'PUT',
            'RED', 'RUN', 'SET', 'SIT', 'SIX', 'TEN', 'TRY', 'TWO', 'WHY', 'ADD',
            'STOCK', 'SHARE', 'NSE', 'BSE', 'INDIA', 'LIMITED', 'LTD', 'PVT',
            'INC', 'CORP', 'COMPANY', 'PRICE', 'OPEN', 'HIGH', 'LOW', 'CLOSE',
            'VOLUME', 'TOTAL', 'DATE', 'TIME', 'YEAR', 'MONTH', 'WEEK', 'NAME',
            'CODE', 'BUY', 'SELL', 'HOLD', 'TARGET', 'RECOMMENDATION', 'RATING',
            'STRONG', 'WEAK', 'NEUTRAL', 'POSITIVE', 'NEGATIVE', 'BULLISH',
            'BEARISH', 'ABOVE', 'BELOW', 'PROFIT', 'LOSS', 'GAIN', 'CHANGE',
            'PERCENT', 'CURRENT', 'PREVIOUS', 'MARKET', 'INDEX', 'NIFTY', 'SENSEX',
            'BANK', 'BANKING', 'AUTO', 'PHARMA', 'FMCG', 'METAL', 'ENERGY',
            'INFRA', 'REALTY', 'MEDIA', 'PSU', 'PRIVATE', 'CAPITAL',
            'SERVICES', 'FINANCE', 'INSURANCE', 'TECHNOLOGY', 'SOFTWARE',
            'ANALYSIS', 'REPORT', 'STOCKS', 'SHARES', 'PORTFOLIO', 'WATCHLIST'
        }
        
        try:
            with pdfplumber.open(filepath) as pdf:
                full_text = ""
                all_words = []
                
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
                        
                        # Also try to extract tables
                        tables = page.extract_tables()
                        for table in tables:
                            for row in table:
                                if row:
                                    for cell in row:
                                        if cell:
                                            all_words.extend(str(cell).split())
                        
                        # Extract words from text
                        all_words.extend(text.split())
                
                # Process all extracted words
                for word in all_words:
                    if not word:
                        continue
                    
                    # Clean the word
                    clean_word = re.sub(r'[^A-Za-z0-9&-]', '', str(word).strip())
                    clean_upper = clean_word.upper()
                    
                    # Skip empty or too short
                    if len(clean_upper) < 2:
                        continue
                    
                    # Check if it's a known symbol (case-insensitive)
                    if clean_upper in known_symbols:
                        if clean_upper not in symbols:
                            symbols.append(clean_upper)
                            continue
                    
                    # Check for exact match in known symbols (original case)
                    if clean_word in known_symbols:
                        if clean_word not in symbols:
                            symbols.append(clean_word)
                            continue
                    
                    # Pattern-based detection for unknown symbols
                    # Must be: 2-20 chars, mostly uppercase, no common words
                    if (clean_upper.isalpha() and 
                        2 <= len(clean_upper) <= 15 and
                        clean_upper not in exclude_words and
                        # Check it's not a common English word
                        not clean_upper.startswith('THE') and
                        not clean_upper.startswith('AND') and
                        not clean_upper.startswith('FOR')):
                        
                        # Additional checks for stock symbol patterns
                        # Indian stocks often have specific patterns
                        is_stock_like = False
                        
                        # Pattern 1: All uppercase, 2-10 chars (like TCS, INFY, WIPRO)
                        if clean_upper.isupper() and 2 <= len(clean_upper) <= 10:
                            is_stock_like = True
                        
                        # Pattern 2: Mixed with specific suffixes (like HDFCBANK, ICICIBANK)
                        bank_suffixes = ['BANK', 'FIN', 'LIFE', 'GENERAL', 'INS']
                        for suffix in bank_suffixes:
                            if clean_upper.endswith(suffix) and len(clean_upper) > len(suffix):
                                is_stock_like = True
                                break
                        
                        # Pattern 3: Contains numbers (like 3MINDIA)
                        if any(c.isdigit() for c in clean_upper) and clean_upper.isalnum():
                            is_stock_like = True
                        
                        if is_stock_like and clean_upper not in symbols:
                            symbols.append(clean_upper)
                
                # Also try regex pattern for stock symbols in structured text
                # Look for patterns like "RELIANCE - Buy" or "TCS: 3500"
                symbol_patterns = [
                    r'\b([A-Z]{2,15})\s*[-:]\s*(?:Buy|Sell|Hold|Target|CMP|Price)',
                    r'\b([A-Z]{2,15})\s*(?:Ltd|Limited|Inc|Corp)\b',
                    r'\b([A-Z]{2,15})\s*\d+(?:\.\d+)?\s*(?:Rs|INR|₹)',
                ]
                
                for pattern in symbol_patterns:
                    matches = re.findall(pattern, full_text, re.IGNORECASE)
                    for match in matches:
                        symbol = match.upper().strip()
                        if (symbol not in symbols and 
                            symbol not in exclude_words and
                            len(symbol) >= 2 and 
                            len(symbol) <= 15):
                            symbols.append(symbol)
                
                logger.info(f"Extracted {len(symbols)} symbols from PDF")
        
        except Exception as e:
            logger.error(f"PDF parsing error: {e}")
            raise Exception(f"Failed to parse PDF file: {str(e)}")
        
        return symbols
    
    def is_valid_symbol(self, symbol):
        """Validate if a string looks like a valid stock symbol."""
        if not symbol:
            return False
        
        symbol = symbol.strip().upper()
        
        # Basic length check
        if len(symbol) < 2 or len(symbol) > 20:
            return False
        
        # Allow alphanumeric, hyphens, ampersands, and dots
        if not all(c.isalnum() or c in '-&.' for c in symbol):
            return False
        
        # Must contain at least one letter
        if not any(c.isalpha() for c in symbol):
            return False
        
        # Common non-stock words to exclude
        invalid_words = {
            'THE', 'AND', 'FOR', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS',
            'ONE', 'OUR', 'OUT', 'ARE', 'HAS', 'HIS', 'HOW', 'ITS', 'MAY', 'NEW',
            'NOW', 'OLD', 'SEE', 'WAY', 'WHO', 'BOY', 'DID', 'GET', 'HIM', 'LET',
            'SAY', 'SHE', 'TOO', 'USE', 'DAD', 'MOM', 'SIR', 'DAY', 'HAD', 'HIT',
            'MAN', 'RAN', 'SAT', 'TOP', 'WIN', 'YES', 'YET', 'AGO', 'BAD', 'BIG',
            'END', 'FAR', 'FEW', 'GOT', 'HOT', 'JOB', 'LOT', 'OWN', 'PUT',
            'RED', 'RUN', 'SET', 'SIT', 'SIX', 'TEN', 'TRY', 'TWO', 'WHY', 'ADD',
            'STOCK', 'SHARE', 'NSE', 'BSE', 'INDIA', 'LIMITED', 'LTD', 'PVT',
            'INC', 'CORP', 'COMPANY', 'PRICE', 'OPEN', 'HIGH', 'LOW', 'CLOSE',
            'VOLUME', 'TOTAL', 'DATE', 'TIME', 'YEAR', 'MONTH', 'WEEK', 'NAME',
            'CODE', 'BUY', 'SELL', 'HOLD', 'TARGET', 'RECOMMENDATION', 'RATING',
            'STRONG', 'WEAK', 'NEUTRAL', 'POSITIVE', 'NEGATIVE', 'BULLISH',
            'BEARISH', 'ABOVE', 'BELOW', 'PROFIT', 'LOSS', 'GAIN', 'CHANGE',
            'PERCENT', 'CURRENT', 'PREVIOUS', 'MARKET', 'INDEX', 'NIFTY', 'SENSEX',
            'BANK', 'BANKING', 'AUTO', 'PHARMA', 'FMCG', 'METAL', 'ENERGY',
            'ANALYSIS', 'REPORT', 'STOCKS', 'SHARES', 'PORTFOLIO', 'WATCHLIST',
            'GOOD', 'BEST', 'WORST', 'TOP', 'BOTTOM', 'FIRST', 'LAST',
            'NEXT', 'LAST', 'THIS', 'THAT', 'THESE', 'THOSE', 'SOME', 'MANY',
            'MOST', 'OTHER', 'ANOTHER', 'EACH', 'EVERY', 'BOTH', 'FEWER',
            'MORE', 'LESS', 'MUCH', 'LITTLE', 'GREAT', 'LARGE', 'SMALL',
            'LONG', 'SHORT', 'HIGH', 'LOW', 'FAST', 'SLOW', 'EARLY', 'LATE',
            'BEFORE', 'AFTER', 'DURING', 'WHILE', 'UNTIL', 'SINCE', 'ALWAYS',
            'NEVER', 'OFTEN', 'RARELY', 'USUALLY', 'SOMETIMES', 'GENERALLY',
            'MAINLY', 'MOSTLY', 'PARTLY', 'FULLY', 'COMPLETELY', 'QUITE',
            'RATHER', 'FAIRLY', 'PRETTY', 'VERY', 'EXTREMELY', 'HIGHLY',
            'DEAR', 'HELLO', 'HI', 'HEY', 'GOODBYE', 'BYE', 'PLEASE',
            'THANKS', 'THANK', 'SORRY', 'EXCUSE', 'WELCOME', 'REGARDS',
            'SECTION', 'CHAPTER', 'PAGE', 'TABLE', 'FIGURE', 'GRAPH',
            'CHART', 'DIAGRAM', 'IMAGE', 'PICTURE', 'PHOTO', 'LIST',
            'DETAILS', 'INFORMATION', 'DATA', 'STATISTICS', 'NUMBERS',
            'RESULTS', 'SUMMARY', 'OVERVIEW', 'INTRODUCTION', 'CONCLUSION',
            'REFERENCES', 'APPENDIX', 'ATTACHMENT', 'DOCUMENT', 'FILE',
            'FOLDER', 'DIRECTORY', 'PATH', 'LINK', 'URL', 'ADDRESS',
            'CONTACT', 'EMAIL', 'PHONE', 'FAX', 'MOBILE', 'WEBSITE',
            'ONLINE', 'OFFLINE', 'INTERNET', 'WEB', 'SITE', 'PAGE',
            'HOME', 'ABOUT', 'US', 'THEM', 'HIM', 'HER', 'IT', 'THEY',
            'WE', 'HE', 'SHE', 'ME', 'MY', 'YOUR', 'HIS', 'HER', 'ITS',
            'OUR', 'THEIR', 'MINE', 'YOURS', 'HIS', 'HERS', 'OURS',
            'THEIRS', 'MYSELF', 'YOURSELF', 'HIMSELF', 'HERSELF', 'ITSELF',
            'OURSELVES', 'THEMSELVES', 'WHAT', 'WHICH', 'WHO', 'WHOM',
            'WHOSE', 'WHERE', 'WHEN', 'WHY', 'HOW', 'THIS', 'THAT',
            'THESE', 'THOSE', 'AM', 'IS', 'ARE', 'WAS', 'WERE', 'BE',
            'BEEN', 'BEING', 'HAVE', 'HAS', 'HAD', 'HAVING', 'DO', 'DOES',
            'DID', 'DOING', 'WILL', 'WOULD', 'SHALL', 'SHOULD', 'MAY',
            'MIGHT', 'MUST', 'CAN', 'COULD', 'NEED', 'OUGHT', 'DARE',
            'USED', 'ABLE', 'ABOUT', 'ABOVE', 'ACROSS', 'AFTER', 'AGAIN',
            'AGAINST', 'ALONG', 'AMONG', 'AROUND', 'AT', 'BEFORE', 'BEHIND',
            'BELOW', 'BENEATH', 'BESIDE', 'BESIDES', 'BETWEEN', 'BEYOND',
            'BY', 'DESPITE', 'DOWN', 'DURING', 'EXCEPT', 'FOR', 'FROM',
            'IN', 'INSIDE', 'INTO', 'LIKE', 'NEAR', 'OF', 'OFF', 'ON',
            'ONTO', 'OUT', 'OUTSIDE', 'OVER', 'PAST', 'SINCE', 'THROUGH',
            'THROUGHOUT', 'TO', 'TOWARD', 'UNDER', 'UNDERNEATH', 'UNTIL',
            'UP', 'UPON', 'WITH', 'WITHIN', 'WITHOUT'
        }
        
        if symbol in invalid_words:
            return False
        
        # Additional pattern checks
        # Reject if it looks like a regular word (all lowercase when normalized)
        if symbol.isalpha() and len(symbol) <= 3:
            # Short alpha symbols need to be uppercase (like TCS, INFY)
            if not symbol.isupper():
                return False
        
        return True
    
    def export_watchlist(self):
        """Export watchlist to file."""
        if not self.watchlist:
            messagebox.showwarning("Warning", "Watchlist is empty!")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Export Watchlist",
            defaultextension=".json",
            filetypes=[
                ("JSON files", "*.json"),
                ("CSV files", "*.csv"),
                ("Text files", "*.txt")
            ]
        )
        
        if not filepath:
            return
        
        try:
            if filepath.endswith('.json'):
                with open(filepath, 'w') as f:
                    json.dump(self.watchlist, f, indent=2)
            
            elif filepath.endswith('.csv'):
                with open(filepath, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Symbol'])
                    for symbol in self.watchlist:
                        writer.writerow([symbol])
            
            elif filepath.endswith('.txt'):
                with open(filepath, 'w') as f:
                    for symbol in self.watchlist:
                        f.write(f"{symbol}\n")
            
            messagebox.showinfo("Export Success", 
                              f"Watchlist exported to {os.path.basename(filepath)}")
            self.info_label.config(text=f"Exported watchlist to {os.path.basename(filepath)}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {str(e)}")
    
    def export_results(self):
        """Export scan results to Excel."""
        if not self.results:
            messagebox.showwarning("Warning", "No results to export! Run a scan first.")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Export Results",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")]
        )
        
        if not filepath:
            return
        
        try:
            if filepath.endswith('.xlsx'):
                self.export_to_excel(filepath)
            else:
                self.export_to_csv(filepath)
            
            messagebox.showinfo("Export Success",
                              f"Results exported to {os.path.basename(filepath)}")
            self.info_label.config(text=f"Exported results to {os.path.basename(filepath)}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {str(e)}")
    
    def export_to_excel(self, filepath):
        """Export results to formatted Excel file."""
        wb = Workbook()
        ws = wb.active
        ws.title = "Stock Analysis Results"
        
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="0F3460", end_color="0F3460",
                                 fill_type="solid")
        
        rec_colors = {
            "STRONG BUY": PatternFill(start_color="00B894", end_color="00B894", fill_type="solid"),
            "BUY": PatternFill(start_color="55EFC4", end_color="55EFC4", fill_type="solid"),
            "HOLD": PatternFill(start_color="FFEAA7", end_color="FFEAA7", fill_type="solid"),
            "SELL": PatternFill(start_color="FAB1A0", end_color="FAB1A0", fill_type="solid"),
            "STRONG SELL": PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid")
        }
        
        # Title
        ws.merge_cells('A1:K1')
        ws['A1'] = 'Indian Stock Technical Analysis Report v2.0'
        ws['A1'].font = Font(bold=True, size=16, color="0F3460")
        ws['A1'].alignment = Alignment(horizontal='center')
        
        ws.merge_cells('A2:K2')
        ws['A2'] = f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        ws['A2'].alignment = Alignment(horizontal='center')
        
        headers = ['Symbol', 'Price', 'Change%', 'RSI', 'SuperTrend', 'VWAP',
                  'Score', 'Recommendation', 'Stop Loss', 'Target 1', 'Target 2']
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
        
        for row_idx, result in enumerate(self.results, 5):
            ws.cell(row=row_idx, column=1, value=result['symbol'])
            ws.cell(row=row_idx, column=2, value=round(result['price'], 2))
            ws.cell(row=row_idx, column=3, value=round(result['change'], 2))
            ws.cell(row=row_idx, column=4, value=round(result['rsi'], 2))
            ws.cell(row=row_idx, column=5, value=result.get('supertrend_signal', 'N/A'))
            ws.cell(row=row_idx, column=6, value=result.get('vwap_signal', 'N/A'))
            ws.cell(row=row_idx, column=7, value=result['score'])
            
            rec_cell = ws.cell(row=row_idx, column=8, value=result['recommendation'])
            if result['recommendation'] in rec_colors:
                rec_cell.fill = rec_colors[result['recommendation']]
                if result['recommendation'] in ['SELL', 'STRONG SELL']:
                    rec_cell.font = Font(color="FFFFFF", bold=True)
            
            # Add targets
            targets = result.get('targets', {})
            ws.cell(row=row_idx, column=9, value=targets.get('stop_loss', 'N/A'))
            ws.cell(row=row_idx, column=10, value=targets.get('target1', 'N/A'))
            ws.cell(row=row_idx, column=11, value=targets.get('target2', 'N/A'))
        
        for col in range(1, len(headers) + 1):
            max_length = 0
            for row in ws.iter_rows(min_col=col, max_col=col):
                for cell in row:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
            ws.column_dimensions[get_column_letter(col)].width = min(max_length + 2, 50)
        
        wb.save(filepath)
        logger.info(f"Exported results to Excel: {filepath}")
    
    def export_to_csv(self, filepath):
        """Export results to CSV file."""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Symbol', 'Price', 'Change%', 'RSI', 'SuperTrend', 'VWAP',
                           'Score', 'Recommendation', 'Stop Loss', 'Target 1', 'Target 2'])
            for result in self.results:
                targets = result.get('targets', {})
                writer.writerow([
                    result['symbol'],
                    round(result['price'], 2),
                    round(result['change'], 2),
                    round(result['rsi'], 2),
                    result.get('supertrend_signal', 'N/A'),
                    result.get('vwap_signal', 'N/A'),
                    result['score'],
                    result['recommendation'],
                    targets.get('stop_loss', 'N/A'),
                    targets.get('target1', 'N/A'),
                    targets.get('target2', 'N/A')
                ])
        logger.info(f"Exported results to CSV: {filepath}")
    
    def start_scan(self):
        """Start scanning stocks in background thread."""
        if not self.watchlist:
            messagebox.showwarning("Warning", "Watchlist is empty! Add stocks first.")
            return
        
        if self.is_scanning:
            messagebox.showinfo("Info", "Scan already in progress!")
            return
        
        self.is_scanning = True
        self.scan_btn.config(state=tk.DISABLED, text="Scanning...")
        self.results = []
        self.results_tree.delete(*self.results_tree.get_children())
        
        thread = threading.Thread(target=self.scan_stocks, daemon=True)
        thread.start()
        logger.info(f"Started scanning {len(self.watchlist)} stocks")
    
    def scan_stocks(self):
        """Scan all stocks in watchlist with thread-safe GUI updates."""
        total = len(self.watchlist)
        
        for idx, symbol in enumerate(self.watchlist):
            try:
                # Use thread-safe GUI update
                self.gui_manager.schedule(
                    self.update_scan_status,
                    f"Scanning {symbol} ({idx+1}/{total})...",
                    (idx/total)*100
                )
                
                df = self.analyzer.fetch_stock_data(symbol)
                
                if df is None or df.empty or len(df) < 30:  # Reduced minimum from 50 to 30
                    self.gui_manager.schedule(
                        self.add_error_result,
                        symbol,
                        "Insufficient data"
                    )
                    continue
                
                indicators = self.analyzer.calculate_all_indicators(df)
                score_data = self.scorer.calculate_total_score(indicators)
                
                # Calculate change %
                prev_close = safe_float(indicators['prev_close'])
                current_price = safe_float(indicators['current_price'])
                change = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
                
                # Calculate targets
                targets = self.target_calculator.calculate_targets(indicators, score_data['recommendation'])
                
                # Get SuperTrend and VWAP signals
                supertrend = indicators.get('supertrend', {})
                vwap = indicators.get('vwap', {})
                
                result = {
                    'symbol': symbol,
                    'price': current_price,
                    'change': change,
                    'rsi': safe_float(indicators['rsi']),
                    'macd': safe_float(indicators['macd']['histogram']),
                    'macd_signal': 'Bullish' if safe_float(indicators['macd']['histogram']) > 0 else 'Bearish',
                    'score': score_data['total'],
                    'recommendation': score_data['recommendation'],
                    'breakdown': score_data['breakdown'],
                    'indicators': indicators,
                    'targets': targets,
                    'supertrend_signal': supertrend.get('signal', 'N/A'),
                    'supertrend_direction': supertrend.get('direction', 'N/A'),
                    'vwap_signal': vwap.get('signal', 'N/A'),
                    'vwap_position': vwap.get('position', 'N/A')
                }
                
                self.results.append(result)
                
                # Thread-safe GUI update
                self.gui_manager.schedule(
                    self.add_result_to_tree,
                    result
                )
                
                time.sleep(0.5)
                
            except Exception as e:
                error_msg = str(e)[:50]
                self.gui_manager.schedule(
                    self.add_error_result,
                    symbol,
                    error_msg
                )
                logger.error(f"Error scanning {symbol}: {e}")
        
        # Sort results by score
        self.results.sort(key=lambda x: x['score'], reverse=True)
        
        # Complete scan
        self.gui_manager.schedule(self.scan_complete)
    
    def update_scan_status(self, message, progress):
        """Update scan status in GUI."""
        self.status_label.config(text=message)
        self.progress['value'] = progress
        self.info_label.config(text=message)
    
    def add_result_to_tree(self, result):
        """Add a result to the treeview."""
        tags = {
            'STRONG BUY': 'strong_buy',
            'BUY': 'buy',
            'HOLD': 'hold',
            'SELL': 'sell',
            'STRONG SELL': 'strong_sell'
        }
        
        tag = tags.get(result['recommendation'], '')
        
        self.results_tree.insert('', tk.END, values=(
            result['symbol'],
            f"{result['price']:.2f}",
            f"{result['change']:+.2f}%",
            f"{result['rsi']:.1f}",
            result.get('supertrend_signal', 'N/A'),
            result.get('vwap_signal', 'N/A'),
            f"{result['score']:.1f}/100",
            result['recommendation']
        ), tags=(tag,))
        
        self.results_tree.tag_configure('strong_buy', background='#00b894', foreground='white')
        self.results_tree.tag_configure('buy', background='#55efc4', foreground='black')
        self.results_tree.tag_configure('hold', background='#ffeaa7', foreground='black')
        self.results_tree.tag_configure('sell', background='#fab1a0', foreground='black')
        self.results_tree.tag_configure('strong_sell', background='#e74c3c', foreground='white')
    
    def add_error_result(self, symbol, error):
        """Add error entry to treeview."""
        self.results_tree.insert('', tk.END, values=(
            symbol, 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', f'Error: {error}'
        ), tags=('error',))
        self.results_tree.tag_configure('error', background='#636e72', foreground='white')
    
    def scan_complete(self):
        """Handle scan completion."""
        self.is_scanning = False
        self.scan_btn.config(state=tk.NORMAL, text="Scan All Stocks")
        self.progress['value'] = 100
        self.status_label.config(text="Scan Complete!")
        
        self.notebook.select(1)
        
        if self.results:
            strong_buy = sum(1 for r in self.results if r['recommendation'] == 'STRONG BUY')
            buy = sum(1 for r in self.results if r['recommendation'] == 'BUY')
            hold = sum(1 for r in self.results if r['recommendation'] == 'HOLD')
            sell = sum(1 for r in self.results if r['recommendation'] == 'SELL')
            strong_sell = sum(1 for r in self.results if r['recommendation'] == 'STRONG SELL')
            
            cache_stats = self.analyzer.cache.get_stats()
            
            summary = (f"Scan Complete! Strong Buy: {strong_buy} | Buy: {buy} | "
                      f"Hold: {hold} | Sell: {sell} | Strong Sell: {strong_sell}\n"
                      f"Cache: {cache_stats['valid']} valid, {cache_stats['expired']} expired")
            
            self.info_label.config(text=summary)
            messagebox.showinfo("Scan Complete", summary)
            logger.info(f"Scan complete: {len(self.results)} stocks analyzed")
    
    def show_breakdown(self, event):
        """Show score breakdown and targets for selected stock."""
        selection = self.results_tree.selection()
        
        if not selection:
            return
        
        item = self.results_tree.item(selection[0])
        symbol = item['values'][0]
        
        result = next((r for r in self.results if r['symbol'] == symbol), None)
        
        if not result:
            return
        
        # Update breakdown tab
        self.update_breakdown_tab(result)
        
        # Update targets tab
        self.update_targets_tab(result)
        
        # Switch to breakdown tab
        self.notebook.select(2)
    
    def update_breakdown_tab(self, result):
        """Update the breakdown tab with stock details."""
        for widget in self.breakdown_frame.winfo_children():
            widget.destroy()
        
        symbol = result['symbol']
        
        header = tk.Label(self.breakdown_frame,
                         text=f"Score Breakdown: {symbol}",
                         bg='#16213e', fg='#00d4ff',
                         font=('Helvetica', 16, 'bold'))
        header.pack(pady=10)
        
        score = result['score']
        if score >= 75:
            score_color = '#00b894'
        elif score >= 60:
            score_color = '#55efc4'
        elif score >= 45:
            score_color = '#ffeaa7'
        elif score >= 30:
            score_color = '#fab1a0'
        else:
            score_color = '#e74c3c'
        
        overall = tk.Label(self.breakdown_frame,
                          text=f"Overall Score: {score}/100 - {result['recommendation']}",
                          bg='#16213e', fg=score_color,
                          font=('Helvetica', 14, 'bold'))
        overall.pack(pady=5)
        
        price_info = tk.Label(self.breakdown_frame,
                             text=f"Price: {result['price']:.2f} | Change: {result['change']:+.2f}%",
                             bg='#16213e', fg='white',
                             font=('Helvetica', 11))
        price_info.pack(pady=5)
        
        # SuperTrend & VWAP info
        st_vwap_frame = tk.Frame(self.breakdown_frame, bg='#16213e')
        st_vwap_frame.pack(pady=5)
        
        st_info = tk.Label(st_vwap_frame,
                          text=f"SuperTrend: {result.get('supertrend_signal', 'N/A')} ({result.get('supertrend_direction', 'N/A')})",
                          bg='#16213e', fg='#00cec9',
                          font=('Helvetica', 11))
        st_info.pack(side=tk.LEFT, padx=20)
        
        vwap_info = tk.Label(st_vwap_frame,
                            text=f"VWAP: {result.get('vwap_signal', 'N/A')} ({result.get('vwap_position', 'N/A')})",
                            bg='#16213e', fg='#fd79a8',
                            font=('Helvetica', 11))
        vwap_info.pack(side=tk.LEFT, padx=20)
        
        breakdown = result.get('breakdown', {})
        
        bars_frame = tk.Frame(self.breakdown_frame, bg='#16213e')
        bars_frame.pack(fill=tk.X, padx=50, pady=20)
        
        indicator_names = {
            'rsi': 'RSI (14)',
            'macd': 'MACD',
            'moving_averages': 'Moving Averages',
            'bollinger': 'Bollinger Bands',
            'stochastic': 'Stochastic',
            'adx': 'ADX (Trend)',
            'volume': 'Volume (OBV)',
            'momentum': 'Momentum',
            'supertrend': 'SuperTrend',
            'vwap': 'VWAP'
        }
        
        for key, value in breakdown.items():
            row = tk.Frame(bars_frame, bg='#16213e')
            row.pack(fill=tk.X, pady=3)
            
            name = indicator_names.get(key, key)
            label = tk.Label(row, text=f"{name}:",
                           bg='#16213e', fg='white',
                           font=('Helvetica', 10),
                           width=20, anchor=tk.W)
            label.pack(side=tk.LEFT, padx=5)
            
            bar_canvas = tk.Canvas(row, height=20, bg='#0f3460',
                                  highlightthickness=0)
            bar_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            bar_width = int(value * 2)
            if value >= 70:
                bar_color = '#00b894'
            elif value >= 50:
                bar_color = '#55efc4'
            elif value >= 30:
                bar_color = '#ffeaa7'
            else:
                bar_color = '#e74c3c'
            
            bar_canvas.create_rectangle(0, 0, bar_width, 20, fill=bar_color)
            
            score_label = tk.Label(row, text=f"{value}/100",
                                  bg='#16213e', fg='white',
                                  font=('Helvetica', 10, 'bold'),
                                  width=8)
            score_label.pack(side=tk.LEFT, padx=5)
    
    def update_targets_tab(self, result):
        """Update the targets tab with stop-loss and target prices."""
        for widget in self.targets_frame.winfo_children():
            widget.destroy()
        
        symbol = result['symbol']
        targets = result.get('targets', {})
        recommendation = result.get('recommendation', 'HOLD')
        
        # Main container
        main_container = tk.Frame(self.targets_frame, bg='#16213e')
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        header = tk.Label(main_container,
                         text=f"Stop-Loss & Targets: {symbol}",
                         bg='#16213e', fg='#00d4ff',
                         font=('Helvetica', 18, 'bold'))
        header.pack(pady=(10, 15))
        
        # Current price
        current_price = targets.get('current_price', 0)
        price_frame = tk.Frame(main_container, bg='#0f3460', relief=tk.RAISED, bd=2)
        price_frame.pack(fill=tk.X, padx=50, pady=10)
        
        price_label = tk.Label(price_frame,
                              text=f"Current Price: {current_price:.2f}",
                              bg='#0f3460', fg='white',
                              font=('Helvetica', 16, 'bold'))
        price_label.pack(pady=15)
        
        # Recommendation
        rec = recommendation
        rec_color = '#00b894' if rec in ['STRONG BUY', 'BUY'] else '#e74c3c' if rec in ['SELL', 'STRONG SELL'] else '#ffeaa7'
        position = targets.get('position', 'N/A')
        
        rec_frame = tk.Frame(main_container, bg='#16213e')
        rec_frame.pack(fill=tk.X, padx=50, pady=5)
        
        rec_label = tk.Label(rec_frame,
                            text=f"Recommendation: {rec}",
                            bg='#16213e', fg=rec_color,
                            font=('Helvetica', 14, 'bold'))
        rec_label.pack(side=tk.LEFT)
        
        pos_label = tk.Label(rec_frame,
                            text=f"Position: {position}",
                            bg='#16213e', fg='#8892b0',
                            font=('Helvetica', 12))
        pos_label.pack(side=tk.RIGHT)
        
        # Stop Loss
        sl_frame = tk.LabelFrame(main_container, text="STOP LOSS (Exit if price falls below)",
                                bg='#16213e', fg='#e74c3c',
                                font=('Helvetica', 12, 'bold'))
        sl_frame.pack(fill=tk.X, padx=50, pady=10)
        
        sl_value = targets.get('stop_loss', 0)
        sl_display = f"{sl_value:.2f}" if isinstance(sl_value, (int, float)) else str(sl_value)
        
        sl_price = tk.Label(sl_frame,
                           text=sl_display,
                           bg='#16213e', fg='#e74c3c',
                           font=('Helvetica', 20, 'bold'))
        sl_price.pack(pady=15)
        
        risk_amt = targets.get('risk_amount', 0)
        if risk_amt and current_price > 0:
            risk_label = tk.Label(sl_frame,
                                 text=f"Risk per share: {risk_amt:.2f} ({(risk_amt/current_price*100):.1f}%)",
                                 bg='#16213e', fg='#fab1a0',
                                 font=('Helvetica', 10))
            risk_label.pack(pady=(0, 10))
        
        # Targets
        targets_info = [
            ("TARGET 1 (Conservative)", targets.get('target1', 0), '#55efc4', 'First target - book partial profits'),
            ("TARGET 2 (Moderate)", targets.get('target2', 0), '#00b894', 'Main target - book 50% profits'),
            ("TARGET 3 (Aggressive)", targets.get('target3', 0), '#00cec9', 'Maximum target - trail stop loss')
        ]
        
        for label_text, target, color, description in targets_info:
            frame_box = tk.LabelFrame(main_container, text=label_text,
                                 bg='#16213e', fg=color,
                                 font=('Helvetica', 11, 'bold'))
            frame_box.pack(fill=tk.X, padx=50, pady=5)
            
            target_display = f"{target:.2f}" if isinstance(target, (int, float)) else str(target)
            
            price = tk.Label(frame_box,
                            text=target_display,
                            bg='#16213e', fg=color,
                            font=('Helvetica', 18, 'bold'))
            price.pack(pady=10)
            
            desc = tk.Label(frame_box,
                           text=description,
                           bg='#16213e', fg='#8892b0',
                           font=('Helvetica', 9, 'italic'))
            desc.pack(pady=(0, 10))
        
        # Risk-Reward Analysis
        rr_frame = tk.LabelFrame(main_container, text="RISK-REWARD ANALYSIS",
                                bg='#16213e', fg='#fdcb6e',
                                font=('Helvetica', 14, 'bold'))
        rr_frame.pack(fill=tk.X, padx=50, pady=10)
        
        risk_amount = targets.get('risk_amount', 0) or 0
        reward_amount = targets.get('reward_amount', 0) or 0
        risk_reward = targets.get('risk_reward', 0) or 0
        
        # Risk-Reward boxes
        rr_ratio_frame = tk.Frame(rr_frame, bg='#16213e')
        rr_ratio_frame.pack(fill=tk.X, pady=15)
        
        # Risk box
        risk_box = tk.Frame(rr_ratio_frame, bg='#e74c3c', relief=tk.RAISED, bd=2)
        risk_box.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
        
        tk.Label(risk_box, text="RISK", bg='#e74c3c', fg='white',
                font=('Helvetica', 12, 'bold')).pack(pady=5)
        tk.Label(risk_box, text=f"{risk_amount:.2f}",
                bg='#e74c3c', fg='white',
                font=('Helvetica', 16, 'bold')).pack(pady=5)
        if current_price > 0:
            tk.Label(risk_box, text=f"{(risk_amount/current_price*100):.1f}%",
                    bg='#e74c3c', fg='#fab1a0',
                    font=('Helvetica', 10)).pack(pady=(0, 10))
        
        # Arrow
        tk.Label(rr_ratio_frame, text="--->",
                bg='#16213e', fg='white',
                font=('Helvetica', 20, 'bold')).pack(side=tk.LEFT, padx=10)
        
        # Reward box
        reward_box = tk.Frame(rr_ratio_frame, bg='#00b894', relief=tk.RAISED, bd=2)
        reward_box.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
        
        tk.Label(reward_box, text="REWARD", bg='#00b894', fg='white',
                font=('Helvetica', 12, 'bold')).pack(pady=5)
        tk.Label(reward_box, text=f"{reward_amount:.2f}",
                bg='#00b894', fg='white',
                font=('Helvetica', 16, 'bold')).pack(pady=5)
        if current_price > 0:
            tk.Label(reward_box, text=f"{(reward_amount/current_price*100):.1f}%",
                    bg='#00b894', fg='#55efc4',
                    font=('Helvetica', 10)).pack(pady=(0, 10))
        
        # Risk:Reward Ratio
        rr_display_frame = tk.Frame(rr_frame, bg='#16213e')
        rr_display_frame.pack(fill=tk.X, pady=15)
        
        tk.Label(rr_display_frame, text="Risk : Reward Ratio",
                bg='#16213e', fg='#8892b0',
                font=('Helvetica', 12)).pack()
        
        rr_value = f"1 : {risk_reward:.2f}" if risk_reward > 0 else "N/A"
        
        # Color based on ratio
        if risk_reward >= 2:
            rr_color = '#00b894'
            rr_quality = "EXCELLENT"
        elif risk_reward >= 1.5:
            rr_color = '#55efc4'
            rr_quality = "GOOD"
        elif risk_reward >= 1:
            rr_color = '#ffeaa7'
            rr_quality = "ACCEPTABLE"
        else:
            rr_color = '#e74c3c'
            rr_quality = "POOR"
        
        tk.Label(rr_display_frame, text=rr_value,
                bg='#16213e', fg=rr_color,
                font=('Helvetica', 28, 'bold')).pack(pady=5)
        
        tk.Label(rr_display_frame, text=f"Quality: {rr_quality}",
                bg='#16213e', fg=rr_color,
                font=('Helvetica', 14, 'bold')).pack()
        
        # Visual bar for risk-reward
        bar_frame = tk.Frame(rr_frame, bg='#16213e')
        bar_frame.pack(fill=tk.X, padx=20, pady=15)
        
        bar_canvas = tk.Canvas(bar_frame, height=30, bg='#0f3460', highlightthickness=0)
        bar_canvas.pack(fill=tk.X)
        
        # Draw bar after window is visible
        def draw_bar():
            bar_canvas.update_idletasks()
            bar_width = max(bar_canvas.winfo_width(), 400)
            
            if risk_amount > 0 and reward_amount > 0:
                total = risk_amount + reward_amount
                risk_pct = risk_amount / total
                risk_width = int(bar_width * risk_pct)
                
                bar_canvas.delete("all")
                
                # Risk portion
                bar_canvas.create_rectangle(0, 0, risk_width, 30, fill='#e74c3c', outline='')
                bar_canvas.create_text(risk_width//2, 15, 
                                      text=f"Risk {risk_pct*100:.0f}%", 
                                      fill='white', font=('Helvetica', 10, 'bold'))
                
                # Reward portion
                bar_canvas.create_rectangle(risk_width, 0, bar_width, 30, fill='#00b894', outline='')
                bar_canvas.create_text(risk_width + (bar_width-risk_width)//2, 15, 
                                      text=f"Reward {(1-risk_pct)*100:.0f}%", 
                                      fill='white', font=('Helvetica', 10, 'bold'))
        
        self.root.after(100, draw_bar)
        
        # Trading advice
        advice_frame = tk.LabelFrame(main_container, text="Trading Advice",
                                    bg='#16213e', fg='#fdcb6e',
                                    font=('Helvetica', 11, 'bold'))
        advice_frame.pack(fill=tk.X, padx=50, pady=15)
        
        if recommendation in ['STRONG BUY', 'BUY']:
            advice = (
                f"- Enter at current price: {current_price:.2f}\n"
                f"- Keep stop loss at: {sl_display}\n"
                f"- First target: {targets_info[0][1]:.2f}\n"
                f"- Risk only {(risk_amount/current_price*100):.1f}% of capital per trade\n"
                f"- Position size: Based on your risk capital"
            )
        elif recommendation in ['SELL', 'STRONG SELL']:
            advice = (
                f"- Exit long positions at current price: {current_price:.2f}\n"
                f"- Or keep stop loss at: {sl_display}\n"
                f"- Consider short positions if available\n"
                f"- Downside targets available above"
            )
        else:
            advice = (
                f"- Current price: {current_price:.2f}\n"
                f"- Support level: {sl_display}\n"
                f"- Resistance level: {targets_info[0][1]:.2f}\n"
                f"- Wait for breakout direction\n"
                f"- Enter on confirmed breakout with volume"
            )
        
        tk.Label(advice_frame, text=advice,
                bg='#16213e', fg='white',
                font=('Helvetica', 10),
                justify=tk.LEFT).pack(padx=15, pady=15)
        
        # ATR info
        atr_val = targets.get('atr', 0) or 0
        tk.Label(main_container,
                text=f"ATR (14-day volatility): {atr_val:.2f}",
                bg='#16213e', fg='#636e72',
                font=('Helvetica', 9)).pack(pady=10)
        
        # Switch to targets tab
        self.notebook.select(3)


def main():
    """Main entry point."""
    try:
        root = tk.Tk()
        app = StockScannerApp(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"\nError starting application: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Python 3.7+ is installed")
        print("2. Install required packages: pip install yfinance pandas numpy ta openpyxl pdfplumber")
        print("3. For tkinter issues:")
        print("   - Windows: Reinstall Python with 'tcl/tk' option checked")
        print("   - Linux: sudo apt-get install python3-tk")
        print("   - Mac: brew install python-tk")
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
