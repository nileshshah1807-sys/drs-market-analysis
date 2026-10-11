#!/usr/bin/env python3
"""
Score History for DR. NILESH SHAH'S MARKET ANALYSIS
===================================================
Every scan's results are saved to score_history.csv in the data folder - one row per
stock per day (a later scan on the same day replaces that day's earlier rows). The file
opens in Excel.

Used to show how each stock's score and signal changed since the previous scan day,
and to chart a stock's score over time.
"""

import csv
import os
import threading
from datetime import datetime

from app_paths import DATA_DIR

HISTORY_FILE = DATA_DIR / "score_history.csv"
FIELDS = ['date', 'time', 'symbol', 'price', 'score', 'rec', 'rsi', 'rs_3m']
_lock = threading.Lock()


def _read(strict: bool = False) -> list:
    """All saved rows. A file that can't be read gives [] - or, with strict, the error."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, newline='', encoding='utf-8') as f:
            return [row for row in csv.DictReader(f) if row.get('date') and row.get('symbol')]
    except Exception:
        if strict:
            raise
        return []


def record(results, when: datetime = None):
    """Save a scan (result dicts with symbol, price, score, rec, rsi and optional rs)."""
    if not results:
        return
    when = when or datetime.now()
    day, clock = when.strftime('%Y-%m-%d'), when.strftime('%H:%M')
    new = {}
    for r in results:
        rs3 = (r.get('rs') or {}).get('3M')
        new[r['symbol']] = {
            'date': day, 'time': clock, 'symbol': r['symbol'],
            'price': f"{r['price']:.2f}", 'score': f"{r['score']:.1f}", 'rec': r['rec'],
            'rsi': f"{r['rsi']:.1f}", 'rs_3m': '' if rs3 is None else f"{rs3:.2f}",
        }
    with _lock:
        # strict: if the history can't be read right now (e.g. locked by another program), fail
        # this save rather than write today's rows over the whole history
        rows = [row for row in _read(strict=True) if not (row['date'] == day and row['symbol'] in new)]
        rows.extend(new.values())
        rows.sort(key=lambda row: (row['date'], row['symbol']))
        tmp = HISTORY_FILE.with_suffix('.tmp')
        with open(tmp, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp, HISTORY_FILE)


def previous(symbols, before_day: str = None) -> dict:
    """{symbol: row} - each stock's most recent saved scan from an EARLIER day than before_day
    (default: today)."""
    before_day = before_day or datetime.now().strftime('%Y-%m-%d')
    wanted = set(symbols)
    out = {}
    for row in _read():                      # rows are sorted by date, so later ones win
        if row['symbol'] in wanted and row['date'] < before_day:
            out[row['symbol']] = row
    return out


def history(symbol: str) -> list:
    """All saved scans for one stock, oldest first."""
    return [row for row in _read() if row['symbol'] == symbol]
