#!/usr/bin/env python3
"""
Company search for DR. NILESH SHAH'S MARKET ANALYSIS
====================================================
Every company listed on NSE and BSE with its full name and its symbol on each exchange, so
a stock can be found by typing the first letters of the company's name.

The list comes from the exchanges' own files (NSE: main board + SME; BSE: active equities),
joined on the ISIN so a company listed on both is one entry. It ships with the app
(symbols_master.json) and the desktop app refreshes its own copy every week.

    python symbols.py build        download the lists and rewrite symbols_master.json

Each entry: [name, nse, bse, code, mcap, add]
    name   full company name
    nse    NSE symbol ('' if not listed there)
    bse    BSE symbol ('' if not listed there)
    code   BSE scrip code ('' if not listed there)
    mcap   market value in Rs crore (0 if unknown) - bigger companies are listed first
    add    what goes into the watchlist: the symbol that prices are downloaded under
"""

import csv
import io
import json
import logging
import re
import sys
import time
from pathlib import Path

from app_paths import DATA_DIR, RESOURCE_DIR

logger = logging.getLogger(__name__)

MASTER_FILE = RESOURCE_DIR / "symbols_master.json"      # shipped with the app
CACHE_FILE = DATA_DIR / "symbols_cache.json"            # the desktop app's refreshed copy
REFRESH_DAYS = 7
SYMBOL_RE = re.compile(r'^[A-Z0-9][A-Z0-9&_.-]{0,19}$')
NSE_MAIN = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_SME = "https://nsearchives.nseindia.com/emerge/corporates/content/SME_EQUITY_L.csv"
NSE_ETF = "https://nsearchives.nseindia.com/content/equities/eq_etfseclist.csv"
BSE_LIST = ("https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
            "?Group=&Scripcode=&industry=&segment=Equity&status=Active")
NAME, NSE, BSE, CODE, MCAP, ADD = range(6)

_entries = None


# ------------------------------------------------------------
# Building the list from the exchanges
# ------------------------------------------------------------

def _get(url, referer):
    """The exchanges' sites turn away plain scripts, so ask the way a browser does."""
    from curl_cffi import requests as browser
    r = browser.get(url, headers={'Accept': '*/*', 'Referer': referer}, impersonate='chrome', timeout=60)
    r.raise_for_status()
    return r


def _nse_rows(url):
    text = _get(url, 'https://www.nseindia.com/').text
    rows = list(csv.reader(io.StringIO(text)))
    head = [h.strip().upper().replace(' ', '_') for h in rows[0]]
    col = {name: i for i, name in enumerate(head)}
    for row in rows[1:]:
        if len(row) > col['ISIN_NUMBER'] and row[col['SYMBOL']].strip():
            yield row[col['SYMBOL']].strip().upper(), row[col['NAME_OF_COMPANY']].strip(), row[col['ISIN_NUMBER']].strip()


def _tidy(name):
    name = re.sub(r'\s+', ' ', name or '').strip()
    return name[:-1].rstrip() if name.endswith(('-$', '.')) and not name.lower().endswith(('ltd.', 'co.')) else name


_SMALL = {'AND': 'and', 'OF': 'of', 'FOR': 'for', 'THE': 'The'}
_SHORT_WORDS = set("""TATA BANK AUTO GOLD FOOD TECH INFO HOME CARE LIFE STAR ARTS MILL OILS FINE PIPE TUBE WIRE CORP SOFT
    CAST GEMS RICE AGRO ROAD RAIL PORT SHIP LAND CITY PARK FARM FISH MILK IRON ZINC COAL LTD CO NEW ONE AIR OIL GAS SUN BIO
    TEA SRI SHRI SAI JAI JAY RAM OM PVT INC FAB SEA SKY TOP BIG BLUE DEEP EAST WEST REAL TIME TOWN WOOD YARN ZEAL UNI
    NAVA INDO TEXT TYRE PUMP TOOL SEED SALT SOAP SILK WOOL PURE RICH SAFE SURE WISE MEGA MINI MAXI ECO EVER""".split())


def _nice(name):
    """A name the exchange writes in capitals, in ordinary capitalisation. Short words stay as
    they are (they are mostly abbreviations: ITC, NTPC, MRF) unless they are everyday words."""
    if not name.isupper():
        return name
    out = []
    for w in name.split(' '):
        core = w.strip('().,')
        if core in _SMALL:
            out.append(w.replace(core, _SMALL[core]))
        elif core.isalpha() and (len(core) > 4 or core in _SHORT_WORDS):
            out.append(w.replace(core, core.capitalize()))
        else:
            out.append(w)
    text = ' '.join(out)
    return text[:1].upper() + text[1:]


def _etf_rows():
    """NSE's exchange-traded funds: (symbol, a readable name, ISIN). The exchange's own name
    for one is a code (NIPINDETFNIFTYBEES), so it is named after what it tracks: 'Nifty 50 ETF'."""
    text = _get(NSE_ETF, 'https://www.nseindia.com/').content.decode('utf-8', 'replace')
    rows = list(csv.reader(io.StringIO(text)))
    col = {h.strip().upper().replace(' ', ''): i for i, h in enumerate(rows[0])}
    for row in rows[1:]:
        if len(row) <= col['ISINNUMBER'] or not row[col['SYMBOL']].strip():
            continue
        tracks = (row[col['UNDERLYINGKEY']] if len(row) > col.get('UNDERLYINGKEY', 99) else '').strip() or row[col['UNDERLYINGASSET']].strip()
        tracks = re.sub(r'\s+', ' ', tracks)[:48].strip(' -')
        if tracks.isupper() and len(tracks) > 4:
            tracks = tracks.title()
        yield row[col['SYMBOL']].strip().upper(), f"{tracks} ETF" if tracks else 'ETF', row[col['ISINNUMBER']].strip()


def fetch_master():
    """Download and join the lists. Raises if a main one can't be fetched or looks wrong."""
    main = list(_nse_rows(NSE_MAIN))
    sme = list(_nse_rows(NSE_SME))
    bse = _get(BSE_LIST, 'https://www.bseindia.com/').json()
    if len(main) < 1500 or len(bse) < 3000:
        raise RuntimeError(f"lists look incomplete (NSE {len(main)}, BSE {len(bse)})")

    by_isin = {}
    for symbol, name, isin in main:
        by_isin[isin] = [_tidy(name), symbol, '', '', 0, symbol]
    for symbol, name, isin in sme:
        # Yahoo Finance lists NSE's SME stocks with -SM on the end (EVENTIONS-SM.NS)
        by_isin.setdefault(isin, [_tidy(name), symbol, '', '', 0, f"{symbol}-SM"])
    try:
        for symbol, name, isin in _etf_rows():        # a bonus: the lists are complete without it
            by_isin.setdefault(isin, [name, symbol, '', '', 0, symbol])
    except Exception as e:
        logger.warning(f"ETF list not added: {e}")
    nse_symbols = {e[NSE] for e in by_isin.values()}

    for row in bse:
        isin, code = (row.get('ISIN_NUMBER') or '').strip(), str(row.get('SCRIP_CD') or '').strip()
        symbol = (row.get('scrip_id') or '').strip().upper()
        # INE... = a company's shares. Other things on BSE (funds, bonds) are left out, except
        # the BSE listing of an ETF that is already in the list from NSE.
        if not code or not (isin.startswith('INE') or isin in by_isin):
            continue
        try:
            mcap = int(float(row.get('Mktcap') or 0))
        except ValueError:
            mcap = 0
        entry = by_isin.get(isin)
        if entry:
            entry[BSE], entry[CODE], entry[MCAP] = symbol, code, mcap
            bse_name = _tidy(row.get('Issuer_Name') or '')
            if entry[NAME].isupper() and bse_name and not bse_name.isupper():
                entry[NAME] = bse_name           # NSE writes some names in capitals; BSE's reads better
            continue
        # BSE only: prices are under its BSE symbol. A handful share that symbol with a different
        # company on NSE; NSE is always tried first, so they would show the wrong company's
        # prices - those few are left out.
        if symbol in nse_symbols:
            continue
        by_isin[isin] = [_tidy(row.get('Issuer_Name') or row.get('Scrip_Name')), '', symbol, code, mcap, symbol]

    entries = [e for e in by_isin.values() if e[NAME] and SYMBOL_RE.match(e[ADD])]
    for e in entries:
        e[NAME] = _nice(e[NAME])
    entries.sort(key=lambda e: (-e[MCAP], e[NAME].lower()))
    return entries


def build(path=None):
    entries = fetch_master()
    path = Path(path or Path(__file__).resolve().parent / "symbols_master.json")
    path.write_text(json.dumps({'updated': time.strftime('%Y-%m-%d'), 'companies': entries},
                               ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    return entries


# ------------------------------------------------------------
# Using the list
# ------------------------------------------------------------

def _read(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    entries = data['companies']
    if len(entries) < 1000:
        raise ValueError("list too short")
    return entries


def load(force=False):
    """The list: whichever is newer of the copy this app refreshed and the one it shipped with
    (after an update of the app, the shipped one is the newer until the next weekly refresh)."""
    global _entries
    if _entries is None or force:
        paths = sorted((p for p in (CACHE_FILE, MASTER_FILE) if p.exists()), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in paths:
            try:
                _entries = _read(path)
                break
            except Exception as e:
                logger.warning(f"Company list {path.name} unreadable: {e}")
        else:
            _entries = []
    return _entries


def refresh_if_stale(days=REFRESH_DAYS):
    """Download a fresh list if the saved copy is older than `days` (call off the window's
    thread). Returns True if a new list was saved. Failures leave the old list in use."""
    try:
        if CACHE_FILE.exists() and time.time() - CACHE_FILE.stat().st_mtime < days * 86400:
            return False
        build(CACHE_FILE)
        load(force=True)
        return True
    except Exception as e:
        logger.warning(f"Company list refresh failed (the saved list stays in use): {e}")
        return False


def _key(text):
    return re.sub(r'[^a-z0-9& ]+', ' ', text.lower()).split()


def search(query, limit=10, entries=None):
    """Companies matching what was typed - a symbol, a BSE code, or the first letters of the
    words in the name ('tata mot' finds Tata Motors). Best matches first; among equals,
    bigger companies first (the list is kept in that order)."""
    entries = load() if entries is None else entries
    q = query.strip().lower()
    words = _key(query)
    if not q or not words:
        return []
    compact = q.replace(' ', '')
    found = []
    for i, e in enumerate(entries):
        nse, bse, code = e[NSE].lower(), e[BSE].lower(), e[CODE]
        name_words = _key(e[NAME])
        if compact in (nse, bse, code, e[ADD].lower()):
            rank = 0                                           # the exact symbol or code
        elif nse.startswith(compact) or bse.startswith(compact):
            rank = 1                                           # symbol starts with it
        elif ' '.join(name_words).startswith(' '.join(words)):
            rank = 2                                           # name starts with it
        elif all(any(w.startswith(t) for w in name_words) for t in words):
            rank = 3                                           # each typed word starts a word of the name
        elif len(compact) >= 3 and (compact in nse or compact in bse or compact in ''.join(name_words)):
            rank = 4                                           # appears somewhere
        else:
            continue
        found.append((rank, i, e))
    found.sort(key=lambda t: (t[0], t[1]))
    return [e for _, _, e in found[:limit]]


def name_of(symbol):
    """Full company name for a watchlist symbol ('' if unknown)."""
    s = str(symbol).upper()
    index = getattr(name_of, 'index', None)
    if index is None or name_of.size != len(load()):
        index = {}
        for e in load():
            for k in (e[ADD], e[NSE], e[BSE], e[CODE]):
                if k:
                    index.setdefault(k.upper(), e[NAME])
        name_of.index, name_of.size = index, len(load())
    return index.get(s, '')


if __name__ == '__main__':
    if sys.argv[1:2] == ['build']:
        out = build(sys.argv[2] if len(sys.argv) > 2 else None)
        print(f"{len(out)} companies: {sum(1 for e in out if e[NSE])} on NSE, {sum(1 for e in out if e[BSE])} on BSE, "
              f"{sum(1 for e in out if e[NSE] and e[BSE])} on both")
    else:
        for e in search(' '.join(sys.argv[1:])):
            print(f"{e[NAME]:45.45}  NSE {e[NSE] or '-':12} BSE {e[BSE] or '-':12} {e[CODE]:7} add as {e[ADD]}")
