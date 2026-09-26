#!/usr/bin/env python3
"""
Live Trading Module for DR. NILESH SHAH'S MARKET ANALYSIS
==========================================================
- Live Price Feed (Real-time polling)
- Price Alerts
- Multi-Exchange Support with CORRECT timezone handling
"""

import threading
import time
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Callable, Optional
import warnings
warnings.filterwarnings('ignore')

try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
    DATA_OK = True
except ImportError:
    DATA_OK = False


# ============================================================
# EXCHANGE CONFIGURATION WITH CORRECT TIMEZONES
# ============================================================

EXCHANGES = {
    'NSE': {
        'name': 'National Stock Exchange (India)',
        'suffix': '.NS',
        'currency': 'INR',
        'utc_offset_hours': 5.5,  # IST = UTC+5:30
        'market_hours': {'open': '09:15', 'close': '15:30'},
        'trading_days': [0, 1, 2, 3, 4],  # Mon-Fri
    },
    'BSE': {
        'name': 'Bombay Stock Exchange (India)',
        'suffix': '.BO',
        'currency': 'INR',
        'utc_offset_hours': 5.5,
        'market_hours': {'open': '09:15', 'close': '15:30'},
        'trading_days': [0, 1, 2, 3, 4],
    },
    'NYSE': {
        'name': 'New York Stock Exchange (USA)',
        'suffix': '',
        'currency': 'USD',
        'utc_offset_hours': -4,  # EDT (summer) / -5 EST (winter)
        'market_hours': {'open': '09:30', 'close': '16:00'},
        'trading_days': [0, 1, 2, 3, 4],
    },
    'NASDAQ': {
        'name': 'NASDAQ (USA)',
        'suffix': '',
        'currency': 'USD',
        'utc_offset_hours': -4,  # EDT (summer) / -5 EST (winter)
        'market_hours': {'open': '09:30', 'close': '16:00'},
        'trading_days': [0, 1, 2, 3, 4],
    },
    'LSE': {
        'name': 'London Stock Exchange (UK)',
        'suffix': '.L',
        'currency': 'GBP',
        'utc_offset_hours': 1,  # BST (summer) / 0 GMT (winter)
        'market_hours': {'open': '08:00', 'close': '16:30'},
        'trading_days': [0, 1, 2, 3, 4],
    },
    'TSE': {
        'name': 'Tokyo Stock Exchange (Japan)',
        'suffix': '.T',
        'currency': 'JPY',
        'utc_offset_hours': 9,  # JST
        'market_hours': {'open': '09:00', 'close': '15:00'},
        'trading_days': [0, 1, 2, 3, 4],
    },
    'HKEX': {
        'name': 'Hong Kong Stock Exchange',
        'suffix': '.HK',
        'currency': 'HKD',
        'utc_offset_hours': 8,  # HKT
        'market_hours': {'open': '09:30', 'close': '16:00'},
        'trading_days': [0, 1, 2, 3, 4],
    },
    'CRYPTO': {
        'name': 'Cryptocurrency (24/7)',
        'suffix': '-USD',
        'currency': 'USD',
        'utc_offset_hours': 0,
        'market_hours': {'open': '00:00', 'close': '23:59'},
        'trading_days': [0, 1, 2, 3, 4, 5, 6],  # 7 days
    },
}

# Popular stocks by exchange
EXCHANGE_STOCKS = {
    'NSE': ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'WIPRO', 
            'TATAMOTORS', 'TATASTEEL', 'ADANIENT', 'BHARTIARTL', 'ITC', 'KOTAKBANK',
            'LT', 'MARUTI', 'SUNPHARMA', 'AXISBANK', 'BAJFINANCE', 'HCLTECH', 'TITAN'],
    'BSE': ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'WIPRO',
            'TATAMOTORS', 'TATASTEEL', 'ADANIENT', 'BHARTIARTL', 'ITC', 'KOTAKBANK'],
    'NYSE': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'JPM', 'V', 'JNJ', 'WMT', 'PG',
             'MA', 'UNH', 'HD', 'DIS', 'BAC', 'XOM', 'PFE', 'KO', 'PEP', 'NFLX'],
    'NASDAQ': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'NFLX', 
               'ADBE', 'PYPL', 'INTC', 'CSCO', 'CMCSA', 'PEP', 'AVGO', 'TXN', 'QCOM'],
    'LSE': ['SHEL', 'AZN', 'BP', 'HSBA', 'GSK', 'ULVR', 'RIO', 'BHP', 'BARC', 'LLOY'],
    'TSE': ['7203', '8306', '6758', '9984', '6861', '7267', '8316', '6954', '9433', '7974'],
    'CRYPTO': ['BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD', 'SOL-USD', 
               'DOT-USD', 'DOGE-USD', 'AVAX-USD', 'MATIC-USD'],
}


# ============================================================
# MARKET STATUS - CORRECT TIMEZONE HANDLING
# ============================================================

def get_market_local_time(exchange: str) -> datetime:
    """Get current time in market's local timezone."""
    info = EXCHANGES.get(exchange, {})
    utc_offset = info.get('utc_offset_hours', 0)
    
    # Get current UTC time
    utc_now = datetime.now(timezone.utc)
    
    # Convert to market's local time
    market_tz = timezone(timedelta(hours=utc_offset))
    local_time = utc_now.astimezone(market_tz)
    
    return local_time


def is_market_open(exchange: str) -> dict:
    """Check if market is currently open with CORRECT timezone handling."""
    info = EXCHANGES.get(exchange, {})
    if not info:
        return {'is_open': False, 'status': 'UNKNOWN', 'local_time': 'N/A', 'reason': 'Exchange not found'}
    
    # Get market's local time
    local_time = get_market_local_time(exchange)
    
    # Check trading day (Mon-Fri for most, all week for crypto)
    trading_days = info.get('trading_days', [0, 1, 2, 3, 4])
    if local_time.weekday() not in trading_days:
        return {
            'is_open': False,
            'status': 'CLOSED',
            'local_time': local_time.strftime('%H:%M'),
            'reason': 'Weekend - Market Closed'
        }
    
    # Check market hours
    open_str = info['market_hours']['open']
    close_str = info['market_hours']['close']
    
    open_hour, open_min = map(int, open_str.split(':'))
    close_hour, close_min = map(int, close_str.split(':'))
    
    current_time = local_time.time()
    open_time = datetime.strptime(open_str, '%H:%M').time()
    close_time = datetime.strptime(close_str, '%H:%M').time()
    
    is_open = open_time <= current_time <= close_time
    
    if is_open:
        # Calculate time until close
        close_dt = local_time.replace(hour=close_hour, minute=close_min, second=0)
        time_left = close_dt - local_time
        hours_left = int(time_left.total_seconds() // 3600)
        mins_left = int((time_left.total_seconds() % 3600) // 60)
        reason = f"Closes in {hours_left}h {mins_left}m"
    else:
        if current_time < open_time:
            reason = f"Opens at {open_str}"
        else:
            reason = f"Closed at {close_str}"
    
    return {
        'is_open': is_open,
        'status': 'OPEN' if is_open else 'CLOSED',
        'local_time': local_time.strftime('%H:%M'),
        'reason': reason,
        'open_time': open_str,
        'close_time': close_str,
    }


def get_all_market_status() -> Dict:
    """Get status of all markets."""
    results = {}
    for exchange in EXCHANGES:
        results[exchange] = is_market_open(exchange)
    return results


# ============================================================
# LIVE PRICE FEED
# ============================================================

class LivePriceFeed:
    """Real-time price monitoring using polling."""
    
    def __init__(self, update_interval: int = 60):
        self.update_interval = update_interval
        self.subscriptions = {}
        self.is_running = False
        self.thread = None
        self.callbacks = []
        self._lock = threading.Lock()
    
    def subscribe(self, symbol: str, exchange: str = 'NSE', callback: Callable = None):
        key = f"{symbol}_{exchange}"
        with self._lock:
            self.subscriptions[key] = {
                'symbol': symbol,
                'exchange': exchange,
                'callback': callback,
                'last_price': None,
                'last_update': None,
            }
    
    def unsubscribe(self, symbol: str, exchange: str = 'NSE'):
        key = f"{symbol}_{exchange}"
        with self._lock:
            self.subscriptions.pop(key, None)
    
    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        self.is_running = False
    
    def _monitor_loop(self):
        while self.is_running:
            self._fetch_all_prices()
            time.sleep(self.update_interval)
    
    def _fetch_all_prices(self):
        if not DATA_OK:
            return
        
        with self._lock:
            keys = list(self.subscriptions.keys())
        
        for key in keys:
            try:
                sub = self.subscriptions.get(key)
                if not sub:
                    continue
                
                symbol = sub['symbol']
                exchange = sub['exchange']
                suffix = EXCHANGES.get(exchange, {}).get('suffix', '')
                
                ticker = yf.Ticker(f"{symbol}{suffix}")
                info = ticker.fast_info
                
                if info:
                    price = getattr(info, 'last_price', None)
                    if price:
                        with self._lock:
                            if key in self.subscriptions:
                                self.subscriptions[key]['last_price'] = price
                                self.subscriptions[key]['last_update'] = datetime.now()
                
                time.sleep(0.5)
            except:
                pass
    
    def get_price(self, symbol: str, exchange: str = 'NSE') -> Optional[float]:
        key = f"{symbol}_{exchange}"
        sub = self.subscriptions.get(key)
        return sub['last_price'] if sub else None


# ============================================================
# ALERT SYSTEM
# ============================================================

class AlertType:
    PRICE_ABOVE = 'PRICE_ABOVE'
    PRICE_BELOW = 'PRICE_BELOW'
    SCORE_CHANGE = 'SCORE_CHANGE'
    BREAKOUT_UP = 'BREAKOUT_UP'
    BREAKOUT_DOWN = 'BREAKOUT_DOWN'


class Alert:
    def __init__(self, alert_id, symbol, alert_type, condition_value, exchange='NSE'):
        self.alert_id = alert_id
        self.symbol = symbol
        self.alert_type = alert_type
        self.condition_value = condition_value
        self.exchange = exchange
        self.is_active = True
        self.triggered = False
        self.triggered_at = None
        self.created_at = datetime.now()
        self.last_check_price = None
    
    def to_dict(self):
        return {
            'alert_id': self.alert_id,
            'symbol': self.symbol,
            'alert_type': self.alert_type,
            'condition_value': self.condition_value,
            'exchange': self.exchange,
            'is_active': self.is_active,
            'triggered': self.triggered,
            'triggered_at': str(self.triggered_at) if self.triggered_at else None,
            'created_at': str(self.created_at),
        }


class AlertManager:
    def __init__(self, live_feed=None):
        self.alerts = {}
        self.live_feed = live_feed
        self.alert_history = []
        self._lock = threading.Lock()
        self.alerts_file = Path(__file__).parent / "alerts.json"
        self.load_alerts()
        self.last_scores = {}
    
    def add_alert(self, symbol, alert_type, condition_value, exchange='NSE'):
        alert_id = f"{symbol}_{alert_type}_{int(time.time())}"
        alert = Alert(alert_id, symbol, alert_type, condition_value, exchange)
        with self._lock:
            self.alerts[alert_id] = alert
        self.save_alerts()
        return alert_id
    
    def remove_alert(self, alert_id):
        with self._lock:
            self.alerts.pop(alert_id, None)
        self.save_alerts()
    
    def get_active_alerts(self):
        with self._lock:
            return [a.to_dict() for a in self.alerts.values() if a.is_active]
    
    def get_triggered_alerts(self):
        with self._lock:
            return [a.to_dict() for a in self.alerts.values() if a.triggered]
    
    def save_alerts(self):
        try:
            data = {'alerts': [a.to_dict() for a in self.alerts.values()]}
            with open(self.alerts_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except:
            pass
    
    def load_alerts(self):
        try:
            if self.alerts_file.exists():
                with open(self.alerts_file, 'r') as f:
                    data = json.load(f)
                for ad in data.get('alerts', []):
                    alert = Alert(ad['alert_id'], ad['symbol'], ad['alert_type'], 
                                 ad['condition_value'], ad.get('exchange', 'NSE'))
                    alert.is_active = ad.get('is_active', True)
                    self.alerts[alert.alert_id] = alert
        except:
            pass


# ============================================================
# MULTI-EXCHANGE MANAGER
# ============================================================

class MultiExchangeManager:
    def __init__(self):
        self.exchanges = EXCHANGES
        self.watchlist = {}
    
    def is_market_open(self, exchange):
        return is_market_open(exchange)['is_open']
    
    def get_market_status(self, exchange):
        return is_market_open(exchange)
    
    def get_popular_stocks(self, exchange):
        return EXCHANGE_STOCKS.get(exchange, [])
    
    def fetch_price(self, symbol, exchange='NSE'):
        if not DATA_OK:
            return None
        try:
            suffix = self.exchanges.get(exchange, {}).get('suffix', '')
            ticker = yf.Ticker(f"{symbol}{suffix}")
            info = ticker.fast_info
            if info:
                return {
                    'symbol': symbol,
                    'exchange': exchange,
                    'price': getattr(info, 'last_price', None),
                }
        except:
            pass
        return None


# ============================================================
# LIVE TRADING MANAGER
# ============================================================

class LiveTradingManager:
    def __init__(self):
        self.live_feed = LivePriceFeed(update_interval=60)
        self.alert_manager = AlertManager(self.live_feed)
        self.exchange_manager = MultiExchangeManager()
    
    def initialize(self):
        self.alert_manager.load_alerts()
    
    def start_live_feed(self):
        self.live_feed.start()
    
    def stop_live_feed(self):
        self.live_feed.stop()
    
    def add_price_alert(self, symbol, price, alert_type='PRICE_ABOVE', exchange='NSE'):
        return self.alert_manager.add_alert(symbol, alert_type, price, exchange)
    
    def add_score_alert(self, symbol, threshold=10, exchange='NSE'):
        return self.alert_manager.add_alert(symbol, AlertType.SCORE_CHANGE, threshold, exchange)
    
    def get_alerts(self):
        return {
            'active': self.alert_manager.get_active_alerts(),
            'triggered': self.alert_manager.get_triggered_alerts(),
        }
    
    def get_exchanges(self):
        return list(EXCHANGES.keys())
    
    def get_exchange_stocks(self, exchange):
        return EXCHANGE_STOCKS.get(exchange, [])


# ============================================================
# TEST FUNCTION
# ============================================================

def test_market_status():
    """Test market status with correct timezones."""
    print("=" * 70)
    print("MARKET STATUS TEST - Correct Timezone Handling")
    print("=" * 70)
    
    utc_now = datetime.now(timezone.utc)
    print(f"\nCurrent UTC Time: {utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    for exchange in EXCHANGES:
        info = EXCHANGES[exchange]
        status = is_market_open(exchange)
        local_time = get_market_local_time(exchange)
        
        status_icon = "OPEN" if status['is_open'] else "CLOSED"
        status_color = "✓" if status['is_open'] else "✗"
        
        print(f"{exchange:8} | {info['name']:35} | Local: {local_time.strftime('%H:%M'):5} | {status_icon:6} | {status['reason']}")
    
    print()
    print("=" * 70)


if __name__ == "__main__":
    test_market_status()
