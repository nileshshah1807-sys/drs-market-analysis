#!/usr/bin/env python3
"""
Market Data Module for DR. NILESH SHAH'S MARKET ANALYSIS
========================================================
Fast price history for many stocks at once:

- Downloads all symbols in ONE batch request (instead of one request per stock)
- NSE symbols automatically fall back to BSE (.BO) for BSE-only listings
- Keeps a disk cache (data_cache/) so re-scans only download the last few days
- Detects dividend/split re-adjustments and refetches full history when needed

Usage:
    from market_data import load_history
    data = load_history(['RELIANCE', 'TCS', 'CREATIVE'], years=5)
    df = data['RELIANCE']   # DataFrame with Open, High, Low, Close, Volume
"""

import os
import re
import logging
import pickle
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

from app_paths import DATA_DIR
CACHE_DIR = DATA_DIR / "data_cache"
COLUMNS = ['Open', 'High', 'Low', 'Close', 'Volume']
MIN_ROWS = 20
FRESH_MINUTES = 10          # cached data younger than this is used without any download
BATCH_SIZE = 100            # tickers per yf.download call
ADJUST_TOLERANCE = 0.005    # 0.5% price mismatch on overlapping days => history was re-adjusted

# Yahoo suffixes to try, in order, for each exchange
EXCHANGE_SUFFIXES = {
    'NSE': ['.NS', '.BO'],
    'BSE': ['.BO', '.NS'],   # Yahoo's BSE feed is empty for some large caps (e.g. RELIANCE.BO) - NSE price is near-identical
    'NYSE': [''],
    'NASDAQ': [''],
    'US': [''],
}

_lock = threading.Lock()


# ------------------------------------------------------------
# Disk cache helpers
# ------------------------------------------------------------

def _cache_path(ticker: str) -> Path:
    safe = re.sub(r'[^A-Za-z0-9_.-]', lambda m: f"%{ord(m.group()):02X}", ticker)
    return CACHE_DIR / f"{safe}.pkl"


def _read_cache(ticker: str):
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        with open(path, 'rb') as f:
            entry = pickle.load(f)
        if isinstance(entry, dict) and isinstance(entry.get('df'), pd.DataFrame):
            return entry
    except Exception as e:
        logger.warning(f"Cache read failed for {ticker}: {e}")
    return None


def _write_cache(ticker: str, df: pd.DataFrame, years: int):
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        tmp = _cache_path(ticker).with_suffix('.tmp')
        with open(tmp, 'wb') as f:
            pickle.dump({'df': df, 'years': years, 'saved': datetime.now()}, f)
        os.replace(tmp, _cache_path(ticker))
    except Exception as e:
        logger.warning(f"Cache write failed for {ticker}: {e}")


def clear_cache():
    """Delete all cached price files."""
    if CACHE_DIR.exists():
        for p in CACHE_DIR.glob('*.pkl'):
            try:
                p.unlink()
            except OSError:
                pass


# ------------------------------------------------------------
# Download helpers
# ------------------------------------------------------------

def _clean(df) -> pd.DataFrame:
    """Keep OHLCV columns, drop empty rows, make the index tz-naive dates."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=COLUMNS)
    df = df[[c for c in COLUMNS if c in df.columns]].dropna(subset=['Close'])
    if getattr(df.index, 'tz', None) is not None:
        df.index = df.index.tz_localize(None)
    df = df[~df.index.duplicated(keep='last')].sort_index()
    return df


def _extract(data, ticker: str) -> pd.DataFrame:
    """Pull one ticker's frame out of a yf.download result (layout differs by version/count)."""
    if data is None or len(data) == 0:
        return pd.DataFrame(columns=COLUMNS)
    if isinstance(data.columns, pd.MultiIndex):
        if ticker in data.columns.get_level_values(0):
            return _clean(data[ticker])
        if ticker in data.columns.get_level_values(1):
            return _clean(data.xs(ticker, axis=1, level=1))
        return pd.DataFrame(columns=COLUMNS)
    return _clean(data)


def _download(tickers, **kwargs) -> dict:
    """Batch-download tickers. Returns {ticker: DataFrame} (possibly empty frames)."""
    out = {}
    tickers = list(dict.fromkeys(tickers))
    for i in range(0, len(tickers), BATCH_SIZE):
        chunk = tickers[i:i + BATCH_SIZE]
        try:
            data = yf.download(chunk, group_by='ticker', threads=True, progress=False,
                               auto_adjust=True, **kwargs)
        except Exception as e:
            logger.error(f"Batch download failed ({len(chunk)} tickers): {e}")
            data = None
        for t in chunk:
            out[t] = _extract(data, t)
    return out


def _full_fetch(symbols, suffixes, years, progress=None) -> dict:
    """Download full history, trying each suffix in turn for symbols still missing.
    Returns {symbol: (ticker, df)}."""
    found = {}
    remaining = list(symbols)
    for n, suffix in enumerate(suffixes):
        if not remaining:
            break
        if progress:
            progress(f"Downloading {len(remaining)} stocks ({suffix or 'US'})...")
        frames = _download([s + suffix for s in remaining], period=f"{years}y")
        still = []
        for s in remaining:
            df = frames.get(s + suffix)
            if df is not None and len(df) >= MIN_ROWS:
                found[s] = (s + suffix, df)
            else:
                still.append(s)
        remaining = still
    return found


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def load_history(symbols, years: int = 5, exchange: str = 'NSE', progress=None,
                 force_refresh: bool = False) -> dict:
    """Return {symbol: DataFrame(Open, High, Low, Close, Volume)} for all symbols with data.

    Symbols without data (delisted / invalid) are simply missing from the result.
    """
    suffixes = EXCHANGE_SUFFIXES.get(exchange, [''])
    symbols = [s.strip().upper() for s in symbols if s and s.strip()]
    symbols = list(dict.fromkeys(symbols))
    result = {}
    need_full = []
    need_update = {}   # ticker -> (symbol, cached_df)
    now = datetime.now()

    with _lock:
        # 1. Use the cache where possible
        for s in symbols:
            entry, ticker = None, None
            for suffix in suffixes:
                entry = _read_cache(s + suffix)
                if entry:
                    ticker = s + suffix
                    break
            if (not entry or force_refresh or entry.get('years', 0) < years
                    or len(entry['df']) < MIN_ROWS):
                need_full.append(s)
            elif now - entry['saved'] < timedelta(minutes=FRESH_MINUTES):
                result[s] = entry['df']
            else:
                need_update[ticker] = (s, entry['df'])

        # 2. Incremental update: download only the last few days, one batch per suffix
        by_suffix = {}
        for ticker, (s, df) in need_update.items():
            by_suffix.setdefault(ticker[len(s):], []).append(ticker)
        for suffix, tickers in by_suffix.items():
            if progress:
                progress(f"Updating {len(tickers)} stocks...")
            start = min(need_update[t][1].index[-1] for t in tickers) - timedelta(days=7)
            frames = _download(tickers, start=start.strftime('%Y-%m-%d'))
            for t in tickers:
                s, old = need_update[t]
                new = frames.get(t)
                if new is None or new.empty:
                    result[s] = old   # network hiccup: fall back to cached data
                    continue
                overlap = old.index.intersection(new.index)
                if len(overlap):
                    diff = ((old.loc[overlap, 'Close'] - new.loc[overlap, 'Close']).abs()
                            / old.loc[overlap, 'Close'].abs()).max()
                    if diff > ADJUST_TOLERANCE:
                        need_full.append(s)   # dividend/split re-adjusted history
                        continue
                merged = pd.concat([old[~old.index.isin(new.index)], new]).sort_index()
                cutoff = merged.index[-1] - pd.DateOffset(years=years, days=7)
                merged = merged[merged.index >= cutoff]
                result[s] = merged
                _write_cache(t, merged, years)

        # 3. Full download for new symbols (and re-adjusted ones)
        if need_full:
            for s, (ticker, df) in _full_fetch(need_full, suffixes, years, progress).items():
                result[s] = df
                _write_cache(ticker, df, years)

    return result


def slice_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """Slice a history frame to a yfinance-style period ('1mo', '6mo', '2y', ...)."""
    if df is None or df.empty:
        return df
    m = re.fullmatch(r'(\d+)(mo|y|d|wk)', period)
    if not m:
        return df
    n, unit = int(m.group(1)), m.group(2)
    offset = {'mo': pd.DateOffset(months=n), 'y': pd.DateOffset(years=n),
              'd': pd.DateOffset(days=n), 'wk': pd.DateOffset(weeks=n)}[unit]
    return df[df.index > df.index[-1] - offset]
