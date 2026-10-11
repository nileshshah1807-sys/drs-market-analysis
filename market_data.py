#!/usr/bin/env python3
"""
Market Data Module for DR. NILESH SHAH'S MARKET ANALYSIS
========================================================
Fast price history for many stocks at once:

- Downloads all symbols in ONE batch request (instead of one request per stock)
- NSE symbols automatically fall back to BSE (.BO) for BSE-only listings
- Keeps a disk cache (data_cache/) so re-scans only download the last few days
- Detects dividend/split re-adjustments and refetches full history when needed
- Stocks listed within the last month come with 1-hour candles (load_scan_history)

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
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class _YahooErrorCapture(logging.Handler):
    """Collects yfinance's error messages instead of printing/logging them. They name the
    tickers that failed and why - used to retry tickers Yahoo rate-limited."""
    def __init__(self):
        super().__init__(logging.ERROR)
        self.messages = []
    
    def emit(self, record):
        try:
            self.messages.append(record.getMessage())
        except Exception:
            pass


_yahoo_errors = _YahooErrorCapture()
_yf_logger = logging.getLogger('yfinance')
_yf_logger.handlers = [_yahoo_errors]
_yf_logger.setLevel(logging.ERROR)
_yf_logger.propagate = False      # keep "possibly delisted" etc. out of the app log

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
    'INDEX': [''],          # market indices, e.g. '^NSEI' (Nifty 50)
}

_lock = threading.Lock()


# ------------------------------------------------------------
# Disk cache helpers
# ------------------------------------------------------------

def _cache_path(ticker: str) -> Path:
    safe = re.sub(r'[^A-Za-z0-9_.-]', lambda m: f"%{ord(m.group()):02X}", ticker)
    return CACHE_DIR / f"{safe}.pkl"


# Cache files hold plain numpy arrays (not a pickled DataFrame): a DataFrame pickled by
# pandas with pyarrow installed can't be unpickled where pyarrow is missing (the .exe).
CACHE_FORMAT = 2


def _read_cache(ticker: str):
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        with open(path, 'rb') as f:
            entry = pickle.load(f)
        if isinstance(entry, dict) and entry.get('format') == CACHE_FORMAT:
            df = pd.DataFrame(entry['values'], index=pd.DatetimeIndex(entry['index']), columns=list(entry['columns']))
            return {'df': df, 'years': entry['years'], 'saved': entry['saved']}
        if isinstance(entry, dict) and isinstance(entry.get('df'), pd.DataFrame):
            return entry   # older format - re-saved in the new format on the next update
    except Exception as e:
        # e.g. an old-format file written with pyarrow: treat as a cache miss and download again
        logger.info(f"Cache entry for {ticker} unreadable ({e}); downloading again")
    return None


def _write_cache(ticker: str, df: pd.DataFrame, years: int):
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        tmp = _cache_path(ticker).with_suffix('.tmp')
        with open(tmp, 'wb') as f:
            pickle.dump({'format': CACHE_FORMAT, 'columns': [str(c) for c in df.columns],
                         'index': df.index.values.astype('datetime64[ns]'),
                         'values': df.to_numpy(dtype='float64'),
                         'years': years, 'saved': datetime.now()}, f)
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

def _clean(df, tz=None) -> pd.DataFrame:
    """Keep OHLCV columns, drop empty rows, make the index tz-naive dates.
    `tz`: for intraday candles, the exchange's time zone - their times are kept in it
    (some yfinance versions hand intraday candles back in UTC)."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=COLUMNS)
    df = df[[c for c in COLUMNS if c in df.columns]].dropna(subset=['Close'])
    if getattr(df.index, 'tz', None) is not None:
        if tz:
            df.index = df.index.tz_convert(tz)
        df.index = df.index.tz_localize(None)
    df = df[~df.index.duplicated(keep='last')].sort_index()
    return df


def _extract(data, ticker: str, tz=None) -> pd.DataFrame:
    """Pull one ticker's frame out of a yf.download result (layout differs by version/count)."""
    if data is None or len(data) == 0:
        return pd.DataFrame(columns=COLUMNS)
    if isinstance(data.columns, pd.MultiIndex):
        if ticker in data.columns.get_level_values(0):
            return _clean(data[ticker], tz)
        if ticker in data.columns.get_level_values(1):
            return _clean(data.xs(ticker, axis=1, level=1), tz)
        return pd.DataFrame(columns=COLUMNS)
    return _clean(data, tz)


def _rate_limited_tickers(messages) -> set:
    """Tickers that yfinance reported as rate-limited ("Too Many Requests").
    Its messages look like: ['ABC.NS', 'XYZ.NS']: YFRateLimitError('Too Many Requests...')"""
    limited = set()
    for msg in messages:
        m = re.match(r"\s*\[(.*?)\]:\s*(.*)", msg, re.S)
        if m and ('RateLimit' in m.group(2) or 'Too Many Requests' in m.group(2)):
            limited.update(t.strip(" '\"") for t in m.group(1).split(','))
    return limited


def _download(tickers, tz=None, **kwargs) -> dict:
    """Batch-download tickers. Returns {ticker: DataFrame} (possibly empty frames).
    Tickers Yahoo rate-limited are retried (after 2 s, then 4 s) instead of being reported
    as having no data. `tz`: see _clean (intraday candles only)."""
    out = {}
    tickers = list(dict.fromkeys(tickers))
    for i in range(0, len(tickers), BATCH_SIZE):
        pending, delay = tickers[i:i + BATCH_SIZE], 2
        for attempt in range(3):
            _yahoo_errors.messages = []
            try:
                data = yf.download(pending, group_by='ticker', threads=True, progress=False,
                                   auto_adjust=True, **kwargs)
            except Exception as e:
                logger.error(f"Batch download failed ({len(pending)} tickers): {e}")
                data = None
            for t in pending:
                out[t] = _extract(data, t, tz)
            limited = [t for t in pending if out[t].empty and t in _rate_limited_tickers(_yahoo_errors.messages)]
            if not limited or attempt == 2:
                if limited:
                    logger.warning(f"Yahoo rate limit: no data for {len(limited)} tickers after retries")
                break
            logger.info(f"Yahoo rate limit for {len(limited)} tickers - retrying in {delay} s")
            time.sleep(delay)
            pending, delay = limited, delay * 2
    return out


def _full_fetch(symbols, suffixes, years, progress=None, short=None) -> dict:
    """Download full history, trying each suffix in turn for symbols still missing.
    Returns {symbol: (ticker, df)}. `short`, if given, collects {symbol: df} for symbols
    that have some history but fewer than MIN_ROWS days."""
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
                if short is not None:
                    short.pop(s, None)
            else:
                still.append(s)
                if short is not None and df is not None and len(df):
                    short.setdefault(s, df)
        remaining = still
    return found


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def load_history(symbols, years: int = 5, exchange: str = 'NSE', progress=None,
                 force_refresh: bool = False, short=None) -> dict:
    """Return {symbol: DataFrame(Open, High, Low, Close, Volume)} for all symbols with data.

    Symbols without data (delisted / invalid) are simply missing from the result, and so are
    stocks with fewer than MIN_ROWS days of history; `short` (a dict), if given, is filled
    with those: {symbol: DataFrame}.
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
            for s, (ticker, df) in _full_fetch(need_full, suffixes, years, progress, short).items():
                result[s] = df
                _write_cache(ticker, df, years)

    return result


# ------------------------------------------------------------
# New listings: 1-hour candles
# ------------------------------------------------------------
# A stock listed within the last month has too few daily candles for the indicators (a
# 20-day average needs 20 days), so it is analysed on 1-hour candles instead: NSE and BSE
# have 7 a day, which is enough from the third trading day.

NEW_LISTING_MONTHS = 1               # less daily history than this => 1-hour candles
HOURLY_EXCHANGES = ('NSE', 'BSE')    # both open at 09:15, so the hours run 09:15-10:15, 10:15-11:15, ...
HOURLY_TZ = 'Asia/Kolkata'
# Footnote for reports, where stocks analysed on 1-hour candles get a * after the symbol
HOURLY_NOTE = ("* New listing (under a month old): analysed on 1-hour candles instead of daily ones, "
               "so its stop-loss and targets are closer to the price.")
_CANDLE = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}


def is_hourly(df) -> bool:
    """True if the frame holds 1-hour candles (a new listing) rather than daily ones."""
    return df is not None and len(df) > 0 and bool((df.index != df.index.normalize()).any())


def daily_bars(df, daily=None):
    """One candle per day, for figures that are per day whatever the candle size (the day's
    price change, value traded per day, returns vs the Nifty). Daily history is returned as is.

    1-hour candles are combined into days. `daily`, the stock's own (short) daily history,
    then supplies the exchange's official closing prices and full volumes for the days Yahoo
    has them - the last trade of the day is not quite the official close."""
    if not is_hourly(df):
        return df
    days = df.groupby(df.index.normalize()).agg(_CANDLE)
    if daily is not None and len(daily):
        days = daily.reindex(days.index).combine_first(days)
    return days


def _hourly(df15) -> pd.DataFrame:
    """Combine 15-minute candles into 1-hour candles. Yahoo's own 1-hour candles have the
    same prices, but on NSE they report no volume for the first hour of the day."""
    if df15 is None or df15.empty:
        return pd.DataFrame(columns=COLUMNS)
    return df15.resample('60min', offset='15min').agg(_CANDLE).dropna(subset=['Close'])


def load_scan_history(symbols, years: int = 5, exchange: str = 'NSE', progress=None, days=None) -> dict:
    """load_history(), with new listings added: a stock with less than a month of daily
    history comes back with 1-hour candles instead of daily ones (is_hourly() tells which).
    `days` (a dict), if given, is filled with those stocks' daily candles: {symbol: DataFrame}.

    A stock listed only a day or two ago is returned as well, with fewer than MIN_ROWS candles.
    """
    short = {}
    result = load_history(symbols, years, exchange, progress, short=short)
    if exchange not in HOURLY_EXCHANGES:
        return result
    cutoff = pd.Timestamp(datetime.now()) - pd.DateOffset(months=NEW_LISTING_MONTHS)
    daily = {s: df for s, df in {**short, **result}.items() if df.index[0] > cutoff}
    todo = list(daily)
    for suffix in EXCHANGE_SUFFIXES[exchange]:
        if not todo:
            break
        if progress:
            progress(f"Downloading 1-hour candles for {len(todo)} new listing(s)...")
        with _lock:
            # Yahoo keeps 15-minute candles for 60 days - more than a new listing has
            frames = _download([s + suffix for s in todo], tz=HOURLY_TZ, period='60d', interval='15m')
        still = []
        for s in todo:
            df = _hourly(frames.get(s + suffix))
            if df.empty:
                still.append(s)       # nothing under this suffix - try the other exchange
            elif df.index[0] > cutoff:
                result[s] = df
                if days is not None:
                    days[s] = daily_bars(df, daily[s])
            # else Yahoo has candles older than a month: not a new listing, leave it as it was
        todo = still
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


# ------------------------------------------------------------
# Sectors (Yahoo Finance), cached in data_cache/sectors.json
# ------------------------------------------------------------

SECTOR_RECHECK_DAYS = 30   # stocks Yahoo had no sector for are looked up again after this


def _lookup_sector(symbol: str):
    """Sector name; '' if Yahoo knows the stock but has no sector; None if the lookup failed
    (network/rate limit) - failures aren't cached, so they're retried next time."""
    import time as _time
    import yfinance as _yf
    failed = False
    for suffix in ('.NS', '.BO'):
        info = None
        for attempt in range(2):
            try:
                info = _yf.Ticker(symbol + suffix).info or {}
                break
            except Exception:
                _time.sleep(1)
        if info is None:
            failed = True
            continue
        name = f"{info.get('longName') or ''} {info.get('shortName') or ''}"
        # Yahoo labels Indian ETFs (NIFTYBEES, GOLDBEES...) as plain equities - spot them by name
        if info.get('quoteType') in ('ETF', 'MUTUALFUND') or ' ETF' in f" {name.upper()}" or 'BEES' in name.upper():
            return 'ETFs & Funds'
        if info.get('sector'):
            return info['sector']
        if name.strip():
            return ''          # found, but Yahoo has no sector for it
    return None if failed else ''


def get_sectors(symbols, progress=None) -> dict:
    """{symbol: sector name ('' if unknown)} - looked up once from Yahoo, then cached."""
    import json
    from concurrent.futures import ThreadPoolExecutor
    path = CACHE_DIR / "sectors.json"
    try:
        cache = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        cache = {}
    today = datetime.now().date()
    
    def stale(s):
        entry = cache.get(s)
        if not entry:
            return True
        if entry.get('sector'):
            return False
        try:
            return (today - datetime.strptime(entry.get('checked', ''), '%Y-%m-%d').date()).days > SECTOR_RECHECK_DAYS
        except ValueError:
            return True
    
    todo = [s for s in dict.fromkeys(s.upper() for s in symbols) if stale(s)]
    if todo:
        if progress:
            progress(f"Looking up sectors for {len(todo)} stocks...")
        with ThreadPoolExecutor(max_workers=4) as pool:
            for s, sector in zip(todo, pool.map(_lookup_sector, todo)):
                if sector is not None:          # don't remember failed lookups
                    cache[s] = {'sector': sector, 'checked': today.isoformat()}
        try:
            CACHE_DIR.mkdir(exist_ok=True)
            path.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding='utf-8')
        except Exception as e:
            logger.warning(f"Could not save sector cache: {e}")
    return {s: cache.get(s.upper(), {}).get('sector', '') for s in symbols}
