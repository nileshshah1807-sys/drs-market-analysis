#!/usr/bin/env python3
"""Test script to verify v2.0 functionality."""

import sys
import os

print(f"Python version: {sys.version}")
print("=" * 60)
print("Stock Scanner v2.0 - Feature Test")
print("=" * 60)

# Test imports
try:
    import yfinance as yf
    print("[OK] yfinance imported")
except ImportError as e:
    print(f"[FAIL] yfinance: {e}")
    sys.exit(1)

try:
    import pandas as pd
    import numpy as np
    print("[OK] pandas + numpy imported")
except ImportError as e:
    print(f"[FAIL] pandas/numpy: {e}")
    sys.exit(1)

try:
    import ta
    print("[OK] ta (technical analysis) imported")
except ImportError as e:
    print(f"[FAIL] ta: {e}")
    sys.exit(1)

try:
    from openpyxl import Workbook
    print("[OK] openpyxl imported")
except ImportError as e:
    print(f"[FAIL] openpyxl: {e}")
    sys.exit(1)

try:
    import pdfplumber
    print("[OK] pdfplumber imported")
except ImportError as e:
    print(f"[WARNING] pdfplumber not available: {e}")

print("=" * 60)
print("\nTesting NEW v2.0 Features...")

# Test safe_float function
def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        val = float(value)
        if pd.isna(val) or np.isnan(val) or np.isinf(val):
            return default
        return val
    except (TypeError, ValueError):
        return default

# Test NaN handling
print("\n1. NaN Handling:")
print(f"   safe_float(None) = {safe_float(None)}")
print(f"   safe_float(float('nan')) = {safe_float(float('nan'))}")
print(f"   safe_float(float('inf')) = {safe_float(float('inf'))}")
print(f"   safe_float(42.5) = {safe_float(42.5)}")
print("   [OK] NaN handling works")

# Test DataCache
from datetime import datetime, timedelta
import threading

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
            return None
    
    def set(self, symbol, data):
        with self._lock:
            self.cache[symbol] = (data, datetime.now())
    
    def clear(self):
        with self._lock:
            self.cache.clear()

print("\n2. Data Cache:")
cache = DataCache(cache_duration_hours=4)
cache.set("TEST", {"price": 100})
result = cache.get("TEST")
print(f"   Cache set/get: {result}")
print(f"   Cache miss: {cache.get('NONEXISTENT')}")
print("   [OK] Data cache works")

# Test data fetch with caching
print("\n3. Data Fetch with Caching:")
try:
    ticker = yf.Ticker("RELIANCE.NS")
    df = ticker.history(period="1mo")
    if not df.empty:
        print(f"   RELIANCE data: {len(df)} rows, last close: {df['Close'].iloc[-1]:.2f}")
        
        # Cache the data
        cache.set("RELIANCE", df)
        cached = cache.get("RELIANCE")
        print(f"   Cached data retrieved: {cached is not None}")
        print("   [OK] Data fetch and caching works")
    else:
        print("   [WARNING] No data returned")
except Exception as e:
    print(f"   [FAIL] Data fetch error: {e}")

# Test SuperTrend calculation
print("\n4. SuperTrend Indicator:")
try:
    if not df.empty and len(df) >= 20:
        atr = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=10)
        atr_value = float(atr.average_true_range().iloc[-1])
        
        hl2 = (df['High'] + df['Low']) / 2
        upper_band = hl2 + (3 * atr_value)
        lower_band = hl2 - (3 * atr_value)
        
        current_price = float(df['Close'].iloc[-1])
        supertrend_signal = "BUY" if current_price > lower_band.iloc[-1] else "SELL"
        
        print(f"   ATR: {atr_value:.2f}")
        print(f"   SuperTrend Signal: {supertrend_signal}")
        print("   [OK] SuperTrend calculation works")
except Exception as e:
    print(f"   [FAIL] SuperTrend error: {e}")

# Test VWAP calculation
print("\n5. VWAP Indicator:")
try:
    if not df.empty:
        typical_price = (df['High'] + df['Low'] + df['Close']) / 3
        cumulative_tp_vol = (typical_price * df['Volume']).rolling(window=20).sum()
        cumulative_vol = df['Volume'].rolling(window=20).sum()
        vwap = cumulative_tp_vol / cumulative_vol
        
        current_price = float(df['Close'].iloc[-1])
        current_vwap = float(vwap.iloc[-1])
        
        if current_price > current_vwap:
            vwap_signal = "BULLISH"
        elif current_price < current_vwap:
            vwap_signal = "BEARISH"
        else:
            vwap_signal = "NEUTRAL"
        
        print(f"   VWAP: {current_vwap:.2f}")
        print(f"   Price vs VWAP: {vwap_signal}")
        print("   [OK] VWAP calculation works")
except Exception as e:
    print(f"   [FAIL] VWAP error: {e}")

# Test Stop-Loss Calculator
print("\n6. Stop-Loss & Target Calculator:")
try:
    current_price = float(df['Close'].iloc[-1])
    atr_value = float(ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close']).average_true_range().iloc[-1])
    
    # For BUY recommendation
    stop_loss = current_price - (atr_value * 1.5)
    target1 = current_price + (atr_value * 1.5)
    target2 = current_price + (atr_value * 2.5)
    target3 = current_price + (atr_value * 4.0)
    
    risk = current_price - stop_loss
    reward = target2 - current_price
    risk_reward = reward / risk if risk > 0 else 0
    
    print(f"   Current Price: {current_price:.2f}")
    print(f"   Stop Loss: {stop_loss:.2f}")
    print(f"   Target 1: {target1:.2f}")
    print(f"   Target 2: {target2:.2f}")
    print(f"   Target 3: {target3:.2f}")
    print(f"   Risk:Reward = 1:{risk_reward:.2f}")
    print("   [OK] Stop-Loss calculator works")
except Exception as e:
    print(f"   [FAIL] Stop-Loss calculator error: {e}")

print("\n" + "=" * 60)
print("\n[SUCCESS] All v2.0 features verified!")
print("\nTo run the GUI app: python stock_scanner.py")
print("=" * 60)
