#!/usr/bin/env python3
"""
Corporate Actions Engine v3.0
==============================
Real-time corporate actions scanner for Indian stocks.
Fetches LIVE data from NSE India and BSE India APIs.

Supports ALL corporate action types:
- Dividends
- Stock Splits
- Bonus Issues
- Rights Issues
- Buyback Offers
- Mergers/Amalgamations
- AGM/EGM Dates
- Record Dates
- Ex-Dates

Author: DR. NILESH SHAH'S MARKET ANALYSIS
"""

import os
import sys
import json
import csv
import io
import time
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import pandas as pd
    PD_OK = True
except ImportError:
    PD_OK = False

logger = logging.getLogger(__name__)

# ============================================================
# NSE & BSE API CONFIGURATION
# ============================================================

NSE_BASE = "https://www.nseindia.com"
BSE_BASE = "https://api.bseindia.com"

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8',
    # No 'br': requests can't decode Brotli unless the optional brotli package is installed,
    # and NSE then returns undecodable bytes (-> 0 actions)
    'Accept-Encoding': 'gzip, deflate',
    'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-actions',
}

BSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Referer': 'https://www.bseindia.com/corporates/corporate_act.aspx',
}


def days_until_date(date_str: str) -> Optional[int]:
    """Calendar days from today until a YYYY-MM-DD date (0 = today). None if unparseable."""
    try:
        return (datetime.strptime(date_str, '%Y-%m-%d').date() - datetime.now().date()).days
    except (TypeError, ValueError):
        return None


def extract_amount(purpose: str) -> float:
    """Extract dividend amount from purpose text, e.g. 'Rs. 10', 'Rs.10.50', 'Rs. - 0.4000', 'INR 10', '10.50 per share'."""
    if not purpose:
        return 0.0
    import re
    patterns = [
        r'\b(?:Rs|Re)\.?\s*-?\s*(\d+\.?\d*)',
        r'INR\s*-?\s*(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*per\s*share',
        r'(\d+\.?\d*)\s*\/-',
    ]
    for pattern in patterns:
        match = re.search(pattern, purpose, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return 0.0


# ============================================================
# CORPORATE ACTION TYPES
# ============================================================

ACTION_TYPES = {
    'dividend': ['Dividend', 'DIVIDEND', 'Interim Dividend', 'Final Dividend', 'Special Dividend'],
    'split': ['Stock Split', 'SPLIT', 'Split', 'Sub-division'],
    'bonus': ['Bonus', 'BONUS', 'Bonus Issue', 'Bonus Share'],
    'rights': ['Rights', 'RIGHTS', 'Rights Issue', 'Rights Entitlement'],
    'buyback': ['Buyback', 'BUYBACK', 'Buy Back', 'Buy-Back Offer'],
    'agm': ['AGM', 'Annual General Meeting', 'EGM', 'Extraordinary General Meeting'],
    'merger': ['Merger', 'Amalgamation', 'Scheme of Arrangement', 'Merger/Amalgamation'],
    'record_date': ['Record Date', 'Book Closure'],
    'ex_date': ['Ex-Date', 'Ex-Dividend', 'Ex-Bonus', 'Ex-Split', 'Ex-Rights'],
}


def classify_action(action_str: str) -> str:
    """Classify corporate action type from description."""
    if not action_str:
        return 'other'
    action_lower = action_str.lower()
    
    for category, keywords in ACTION_TYPES.items():
        for kw in keywords:
            if kw.lower() in action_lower:
                return category
    return 'other'


def get_action_icon(category: str) -> str:
    """Get icon for action type."""
    icons = {
        'dividend': '💰',
        'split': '✂️',
        'bonus': '🎁',
        'rights': '📜',
        'buyback': '🔄',
        'agm': '🏛️',
        'merger': '🤝',
        'record_date': '📅',
        'ex_date': '📌',
        'other': '📋',
    }
    return icons.get(category, '📋')


# ============================================================
# NSE CORPORATE ACTIONS FETCHER
# ============================================================

class NSECorporateActions:
    """Fetch corporate actions from NSE India API."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(NSE_HEADERS)
        self._cookies_set = False
        self.unreachable = False   # set when NSE refuses or times out, so callers stop asking
    
    def _ensure_cookies(self):
        """Visit the NSE main page first to pick up cookies.

        Best effort only: the homepage often returns 403 to scripts while the API
        itself still answers, so a failure here must not stop the API call.
        """
        if self._cookies_set:
            return True
        self._cookies_set = True  # only try once per session
        try:
            resp = self.session.get(NSE_BASE, timeout=15)
            if resp.status_code != 200:
                logger.info(f"NSE homepage returned {resp.status_code}; trying API without cookies")
        except Exception as e:
            logger.warning(f"NSE cookie init failed: {e}")
        return True
    
    def fetch_all_actions(self, from_date: str = None, to_date: str = None) -> List[Dict]:
        """Fetch all corporate actions from NSE.
        
        Args:
            from_date: DD-MM-YYYY format (default: 30 days ago)
            to_date: DD-MM-YYYY format (default: 30 days from now)
        
        Returns:
            List of corporate action records
        """
        if not REQUESTS_OK:
            return []
        
        if not self._ensure_cookies():
            return []
        
        if not from_date:
            from_date = (datetime.now() - timedelta(days=30)).strftime('%d-%m-%Y')
        if not to_date:
            to_date = (datetime.now() + timedelta(days=90)).strftime('%d-%m-%Y')
        
        url = f"{NSE_BASE}/api/corporates-corporateActions"
        params = {
            'index': 'equities',
            'from_date': from_date,
            'to_date': to_date,
        }
        
        try:
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_nse_response(data)
            else:
                logger.warning(f"NSE API returned {resp.status_code}")
        except Exception as e:
            logger.error(f"NSE fetch error: {e}")

        self.unreachable = True
        return []
    
    def fetch_symbol_actions(self, symbol: str, from_date: str = None, to_date: str = None) -> List[Dict]:
        """Fetch corporate actions for a specific symbol from NSE."""
        if not REQUESTS_OK:
            return []
        
        if not self._ensure_cookies():
            return []
        
        if not from_date:
            from_date = (datetime.now() - timedelta(days=180)).strftime('%d-%m-%Y')
        if not to_date:
            to_date = (datetime.now() + timedelta(days=365)).strftime('%d-%m-%Y')
        
        url = f"{NSE_BASE}/api/corporates-corporateActions"
        params = {
            'index': 'equities',
            'symbol': symbol,
            'from_date': from_date,
            'to_date': to_date,
        }
        
        try:
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_nse_response(data)
        except Exception as e:
            logger.error(f"NSE symbol fetch error for {symbol}: {e}")

        self.unreachable = True
        return []
    
    def _parse_nse_response(self, data) -> List[Dict]:
        """Parse NSE API response into standardized format."""
        results = []
        
        if not data:
            return results
        
        # NSE returns data under 'data' key
        records = data.get('data', data) if isinstance(data, dict) else data
        
        if not isinstance(records, list):
            return results
        
        for record in records:
            try:
                # Current NSE fields: symbol, comp, series, subject, exDate, recDate, bcStartDate, bcEndDate, faceVal, isin
                # (older responses used purpose/company/recordDate - keep those as fallbacks)
                purpose = record.get('subject') or record.get('purpose') or record.get('Subject') or ''
                ex_date = record.get('exDate') or record.get('ExDate') or ''
                record_date = record.get('recDate') or record.get('recordDate') or record.get('BCrdtDt') or ''
                symbol = record.get('symbol') or record.get('ScripCode') or ''

                # The amount is the dividend per share. Other actions mention rupees too (a split's
                # old face value, a rights issue's premium) - those aren't an amount paid out.
                category = classify_action(purpose)
                amount = self._extract_amount(purpose) if category == 'dividend' else 0.0

                result = {
                    'symbol': symbol,
                    'company': record.get('comp') or record.get('company') or record.get('LONG_NAME') or symbol,
                    'series': record.get('series', 'EQ'),
                    'ex_date': self._format_date(ex_date),
                    'record_date': self._format_date(record_date),
                    'bc_start': self._format_date(record.get('bcStartDate', '')),
                    'bc_end': self._format_date(record.get('bcEndDate', '')),
                    'purpose': purpose,
                    'category': category,
                    'icon': get_action_icon(category),
                    'amount': amount,
                    'source': 'NSE',
                    'raw': record,
                }

                # Calculate days until ex-date
                if result['ex_date']:
                    result['days_until'] = days_until_date(result['ex_date'])
                    if result['days_until'] is not None:
                        result['is_upcoming'] = result['days_until'] >= 0
                        result['is_past'] = result['days_until'] < 0
                    else:
                        result['is_upcoming'] = True
                        result['is_past'] = False
                
                results.append(result)
            except Exception as e:
                logger.warning(f"Parse error: {e}")
                continue
        
        return results
    
    def _extract_amount(self, purpose: str) -> float:
        """Extract dividend amount from purpose string."""
        return extract_amount(purpose)

    def _format_date(self, date_str: str) -> str:
        """Format date to YYYY-MM-DD."""
        if not date_str or str(date_str).strip() == '-':
            return ''

        # Try various formats
        for fmt in ['%d-%b-%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', '%d %b %Y', '%Y-%m-%dT%H:%M:%S']:
            try:
                dt = datetime.strptime(str(date_str).strip(), fmt)
                return dt.strftime('%Y-%m-%d')
            except:
                continue
        
        return str(date_str)


# ============================================================
# BSE CORPORATE ACTIONS FETCHER
# ============================================================

class BSECorporateActions:
    """Fetch corporate actions from BSE India API."""
    
    # The old /CorporateAction/w endpoint now returns an HTML page; DefaultData/w is what
    # bseindia.com's own corporate-actions page uses and returns JSON.
    URL = f"{BSE_BASE}/BseIndiaAPI/api/DefaultData/w"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(BSE_HEADERS)
    
    def fetch_all_actions(self, from_date: str = None, to_date: str = None) -> List[Dict]:
        """Fetch all corporate actions from BSE.
        
        Args:
            from_date: DD/MM/YYYY format (default: 30 days ago)
            to_date: DD/MM/YYYY format (default: 90 days from now)
        
        Returns:
            List of corporate action records
        """
        if not REQUESTS_OK:
            return []
        
        if not from_date:
            from_date = (datetime.now() - timedelta(days=30)).strftime('%d/%m/%Y')
        if not to_date:
            to_date = (datetime.now() + timedelta(days=90)).strftime('%d/%m/%Y')
        
        return self._fetch(from_date, to_date)
    
    def fetch_symbol_actions(self, scrip_code: str, from_date: str = None, to_date: str = None) -> List[Dict]:
        """Fetch corporate actions for a specific BSE scrip code."""
        if not REQUESTS_OK:
            return []
        
        if not from_date:
            from_date = (datetime.now() - timedelta(days=180)).strftime('%d/%m/%Y')
        if not to_date:
            to_date = (datetime.now() + timedelta(days=365)).strftime('%d/%m/%Y')
        
        return self._fetch(from_date, to_date, scrip_code)
    
    def _fetch(self, from_date: str, to_date: str, scrip_code: str = '') -> List[Dict]:
        """Query BSE. Dates are DD/MM/YYYY; the API wants YYYYMMDD."""
        try:
            fdate = datetime.strptime(from_date, '%d/%m/%Y').strftime('%Y%m%d')
            tdate = datetime.strptime(to_date, '%d/%m/%Y').strftime('%Y%m%d')
        except ValueError as e:
            logger.error(f"BSE date error: {e}")
            return []
        
        params = {
            'Fdate': fdate,
            'TDate': tdate,
            'Purposecode': '',
            'ddlcategorys': 'E',
            'ddlindustrys': '',
            'scripcode': scrip_code,
            'segment': '0',
            'strSearch': 'S',
        }
        
        try:
            resp = self.session.get(self.URL, params=params, timeout=30)
            if resp.status_code == 200:
                return self._parse_bse_response(resp.json())
            logger.warning(f"BSE API returned {resp.status_code}")
        except Exception as e:
            logger.error(f"BSE fetch error: {e}")
        return []
    
    def _parse_bse_response(self, data) -> List[Dict]:
        """Parse BSE API response."""
        results = []
        
        if not data:
            return results
        
        records = data if isinstance(data, list) else data.get('Table', data.get('data', []))
        
        if not isinstance(records, list):
            return results
        
        for record in records:
            try:
                # DefaultData fields: scrip_code, short_name, long_name, Ex_date ('01 Sep 2026'),
                # Purpose, RD_Date, BCRD_FROM, BCRD_TO, payment_date
                purpose = record.get('Purpose') or record.get('PURPOSE') or ''
                ex_date = record.get('Ex_date') or record.get('Ex_Date') or record.get('EX_DATE') or ''
                scrip_code = str(record.get('scrip_code') or record.get('SCRIP_CD') or record.get('ScripCode') or '')
                short_name = (record.get('short_name') or '').strip()
                
                category = classify_action(purpose)
                amount = self._extract_amount(purpose) if category == 'dividend' else 0.0   # see the NSE parser

                result = {
                    'symbol': short_name or scrip_code,
                    'scrip_code': scrip_code,
                    'company': (record.get('long_name') or record.get('SCRIP_NAME') or short_name or scrip_code).rstrip('-$').strip(),
                    'series': record.get('SERIES', 'EQ'),
                    'ex_date': self._format_date(ex_date),
                    'record_date': self._format_date(record.get('RD_Date') or record.get('RD_DATE') or ''),
                    'bc_start': self._format_date(record.get('BCRD_FROM') or record.get('BC_FROM') or ''),
                    'bc_end': self._format_date(record.get('BCRD_TO') or record.get('BC_TO') or ''),
                    'purpose': purpose,
                    'category': category,
                    'icon': get_action_icon(category),
                    'amount': amount,
                    'source': 'BSE',
                    'raw': record,
                }
                
                if result['ex_date']:
                    result['days_until'] = days_until_date(result['ex_date'])
                    if result['days_until'] is not None:
                        result['is_upcoming'] = result['days_until'] >= 0
                        result['is_past'] = result['days_until'] < 0
                    else:
                        result['is_upcoming'] = True
                        result['is_past'] = False
                
                results.append(result)
            except Exception as e:
                logger.warning(f"BSE parse error: {e}")
                continue
        
        return results
    
    def _extract_amount(self, purpose: str) -> float:
        """Extract dividend amount."""
        return extract_amount(purpose)
    
    def _format_date(self, date_str: str) -> str:
        """Format date to YYYY-MM-DD."""
        if not date_str or str(date_str).strip() == '-':
            return ''
        for fmt in ['%d-%b-%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', '%d %b %Y', '%Y%m%d']:
            try:
                dt = datetime.strptime(str(date_str).strip(), fmt)
                return dt.strftime('%Y-%m-%d')
            except:
                continue
        return str(date_str)


# ============================================================
# BSE SCRIP CODE MAPPING
# ============================================================

BSE_SCRIP_MAP = {
    'RELIANCE': '500325', 'TCS': '532540', 'HDFCBANK': '500180',
    'INFY': '500209', 'ICICIBANK': '532174', 'HINDUNILVR': '500696',
    'ITC': '500875', 'SBIN': '500112', 'BHARTIARTL': '532454',
    'KOTAKBANK': '500247', 'LT': '500510', 'AXISBANK': '532215',
    'BAJFINANCE': '500034', 'ASIANPAINT': '500820', 'MARUTI': '532500',
    'SUNPHARMA': '524715', 'TITAN': '500114', 'BAJAJFINSV': '532978',
    'WIPRO': '507685', 'HCLTECH': '532281', 'ULTRACEMCO': '532538',
    'NTPC': '532555', 'NESTLEIND': '500790', 'POWERGRID': '532898',
    'TATAMOTORS': '500570', 'TMPV': '500570', 'M&M': '500520', 'JSWSTEEL': '500228',
    'TATASTEEL': '500470', 'TECHM': '532755', 'ADANIENT': '512599',
    'ONGC': '500312', 'HINDALCO': '532230', 'INDUSINDBK': '532187',
    'DIVISLAB': '532488', 'DRREDDY': '500124', 'CIPLA': '500087',
    'GRASIM': '500300', 'BPCL': '500547', 'COALINDIA': '533278',
    'HEROMOTOCO': '500182', 'EICHERMOT': '505200', 'UPL': '512070',
    'TATACONSUM': '500800', 'BAJAJ-AUTO': '532977', 'APOLLOHOSP': '508869',
    'BRITANNIA': '500825', 'PIDILITIND': '500331', 'SBILIFE': '540999',
    'HDFCLIFE': '540777', 'ICICIPRULI': '540133',
    'BALMLAWRIE': '523319', 'NAPEROL': '500298', 'GNFC': '500670',
    'CREATIVE': '539527', 'EMAMIPAPER': '533208', 'EMPIREIND': '509525',
    'VEDL': '500295', 'LTIM': '540251', 'MPHASIS': '526299',
    'PERSISTENT': '533179', 'COFORGE': '532541', 'LTTS': '540115',
    'BEL': '500049', 'HAL': '541154', 'IRCTC': '542830',
    'POLYCAB': '542652', 'HAVELLS': '517354', 'GAIL': '532155',
    'IOC': '530965', 'HINDPETRO': '500104', 'TATAPOWER': '500400',
    'SIEMENS': '500550', 'ABB': '500002', 'BHEL': '500103',
    'DLF': '532868', 'LICI': '543526', 'IRFC': '543257',
    'RVNL': '543005', 'IRCON': '541956', 'NBCC': '534309',
    'RECLTD': '532955', 'PFC': '532810', 'BANDHANBNK': '541153',
    'IDFCFIRSTB': '539437', 'PNB': '532461', 'BANKBARODA': '532134',
    'CANBK': '532483', 'UNIONBANK': '532477', 'FEDERALBNK': '500469',
    'ADANIPORTS': '532921', 'ETERNAL': '543320', 'INDIGO': '539448', 'TRENT': '500251',
}


# ============================================================
# UNIFIED CORPORATE ACTIONS ENGINE
# ============================================================

class CorporateActionsEngine:
    """
    Main engine that scans watchlist stocks for ALL corporate actions.
    Fetches live data from NSE and BSE APIs.
    """
    
    def __init__(self):
        self.nse = NSECorporateActions()
        self.bse = BSECorporateActions()
        self.cache = {}
        self.all_actions = []
        self.symbol_actions = {}
        self._lock = threading.Lock()
        self.last_fetch_time = None
        self.fetch_status = "Not fetched"
        self.fetch_errors = []
    
    def scan_watchlist(self, watchlist: List[str], callback=None) -> Dict:
        """
        Scan ALL watchlist stocks for corporate actions.
        Uses multi-source approach: NSE API -> BSE API -> Local Database -> Yahoo Finance
        
        Args:
            watchlist: List of NSE symbols
            callback: Optional callback(status_msg, progress_pct) for UI updates
        
        Returns:
            Dictionary with symbol -> actions mapping
        """
        self.fetch_errors = []
        self.symbol_actions = {}
        
        total = len(watchlist)
        
        # Step 1: Fetch ALL corporate actions from NSE (bulk fetch)
        if callback:
            callback("Fetching from NSE India...", 5)
        
        nse_actions = []
        try:
            nse_actions = self.nse.fetch_all_actions()
            logger.info(f"NSE: Fetched {len(nse_actions)} corporate actions")
            if callback:
                callback(f"NSE: Found {len(nse_actions)} actions", 20)
        except Exception as e:
            logger.error(f"NSE bulk fetch failed: {e}")
            self.fetch_errors.append(f"NSE: {e}")
        
        # Step 2: Fetch from BSE as backup
        bse_actions = []
        try:
            bse_actions = self.bse.fetch_all_actions()
            logger.info(f"BSE: Fetched {len(bse_actions)} corporate actions")
            if callback:
                callback(f"BSE: Found {len(bse_actions)} actions", 35)
        except Exception as e:
            logger.error(f"BSE bulk fetch failed: {e}")
            self.fetch_errors.append(f"BSE: {e}")
        
        # Step 3: Local database (+ Yahoo history) is used lazily below, only for stocks
        # without live NSE/BSE data - loading it for every stock up front is slow.
        local_ca = None
        try:
            from corporate_actions import CorporateActions as LocalCA
            local_ca = LocalCA()
        except Exception as e:
            logger.warning(f"Local database load failed: {e}")

        # Step 4: Merge all sources and map to watchlist
        all_actions = nse_actions + bse_actions
        
        if callback:
            callback("Processing watchlist stocks...", 55)
        
        watchlist_upper = {s.upper(): s for s in watchlist}
        
        # Index NSE actions by symbol
        nse_by_symbol = {}
        for action in nse_actions:
            sym = action.get('symbol', '').upper()
            if sym in watchlist_upper:
                nse_by_symbol.setdefault(sym, []).append(action)
        
        # For each watchlist stock, build comprehensive action list
        for i, symbol in enumerate(sorted(watchlist)):
            sym_upper = symbol.upper()
            
            if callback:
                pct = 55 + int((i / total) * 40)
                callback(f"Processing {symbol} ({i+1}/{total})...", pct)
            
            symbol_acts = []
            
            # From NSE bulk
            if sym_upper in nse_by_symbol:
                symbol_acts.extend(nse_by_symbol[sym_upper])
            
            # From BSE bulk - match on exact BSE symbol or scrip code. (Substring-matching the
            # company name matched e.g. 'LT' against every '... LTD' company.)
            scrip_code = BSE_SCRIP_MAP.get(sym_upper, sym_upper if sym_upper.isdigit() else None)
            for bse_act in bse_actions:
                bse_sym = bse_act.get('symbol', '').upper()
                if sym_upper == bse_sym or (scrip_code and bse_act.get('scrip_code') == scrip_code):
                    if not any(self._same_event(existing, bse_act) for existing in symbol_acts):
                        symbol_acts.append(bse_act)
            
            # Nothing in the bulk window - ask NSE for this symbol's wider history (live data
            # is better than the local database's estimates, so try this first). Not when NSE
            # has already refused or timed out: every stock would wait for the same failure.
            if not symbol_acts and not self.nse.unreachable:
                try:
                    individual = self.nse.fetch_symbol_actions(symbol)
                    if individual:
                        symbol_acts.extend(individual)
                    time.sleep(0.3)
                except Exception as e:
                    logger.warning(f"Individual fetch failed for {symbol}: {e}")

            # If no live data, use local database
            local = None
            if not symbol_acts and local_ca is not None:
                try:
                    local = local_ca.get_actions(symbol, 'NSE')
                except Exception as e:
                    logger.warning(f"Local lookup failed for {symbol}: {e}")
            if local:
                
                # Convert upcoming events
                for ev in local.get('upcoming_events', []):
                    symbol_acts.append({
                        'symbol': symbol,
                        'company': local.get('name', symbol),
                        'series': 'EQ',
                        'ex_date': ev.get('date', ''),
                        'record_date': '',
                        'bc_start': '',
                        'bc_end': '',
                        'purpose': f"{ev.get('type', 'Dividend')} - Rs.{ev.get('amount', 0):.2f}"
                                   + (" (ESTIMATED - not announced)" if ev.get('estimated') else ""),
                        'category': classify_action(ev.get('type', '')),
                        'icon': get_action_icon(classify_action(ev.get('type', ''))),
                        'amount': ev.get('amount', 0),
                        'source': 'Estimate' if ev.get('estimated') else 'Local DB',
                        'days_until': days_until_date(ev.get('date', '')),
                        'is_upcoming': True,
                        'is_past': False,
                        'estimated': bool(ev.get('estimated')),
                    })
                
                # Convert historical dividends
                for div in local.get('dividends', [])[:5]:
                    date_str = div.get('date', '')
                    is_dup = any(a.get('ex_date') == date_str for a in symbol_acts)
                    if not is_dup:
                        days_until = days_until_date(date_str)

                        symbol_acts.append({
                            'symbol': symbol,
                            'company': local.get('name', symbol),
                            'series': 'EQ',
                            'ex_date': date_str,
                            'record_date': '',
                            'bc_start': '',
                            'bc_end': '',
                            'purpose': f"Dividend - Rs.{div.get('amount', 0):.2f}",
                            'category': 'dividend',
                            'icon': '💰',
                            'amount': div.get('amount', 0),
                            'source': 'Local DB',
                            'days_until': days_until,
                            'is_upcoming': (days_until is not None and days_until >= 0) if days_until is not None else False,
                            'is_past': (days_until is not None and days_until < 0) if days_until is not None else True,
                        })
                
                # Convert splits
                for split in local.get('splits', []):
                    date_str = split.get('date', '')
                    symbol_acts.append({
                        'symbol': symbol,
                        'company': local.get('name', symbol),
                        'series': 'EQ',
                        'ex_date': date_str,
                        'record_date': '',
                        'bc_start': '',
                        'bc_end': '',
                        'purpose': f"Stock Split - Ratio: {split.get('ratio', 'N/A')}",
                        'category': 'split',
                        'icon': '✂️',
                        'amount': 0,
                        'source': 'Local DB',
                        'days_until': None,
                        'is_upcoming': False,
                        'is_past': True,
                    })

            # Sort: upcoming first (by days_until ascending), then past (by date descending)
            # (days_until can be None when the ex-date is missing/unparseable - sort those last)
            upcoming = sorted(
                [a for a in symbol_acts if a.get('is_upcoming', True) and (a.get('days_until') is None or a.get('days_until', 0) >= 0)],
                key=lambda x: x['days_until'] if x.get('days_until') is not None else 9999
            )
            past = sorted(
                [a for a in symbol_acts if a.get('is_past', False) or (a.get('days_until') is not None and a.get('days_until', 0) < 0)],
                key=lambda x: x.get('ex_date', ''), reverse=True
            )
            
            all_sorted = upcoming + past
            
            # Categorize
            categories = {}
            for act in all_sorted:
                cat = act.get('category', 'other')
                categories.setdefault(cat, []).append(act)
            
            self.symbol_actions[symbol] = {
                'symbol': symbol,
                'company': all_sorted[0].get('company', symbol) if all_sorted else symbol,
                'all_actions': all_sorted,
                'upcoming': upcoming,
                'past': past,
                'categories': categories,
                'action_count': len(all_sorted),
                'upcoming_count': len(upcoming),
                'sources': list(set(a.get('source', '') for a in all_sorted)),
            }
        
        self.all_actions = all_actions
        self.last_fetch_time = datetime.now()
        
        if self.fetch_errors:
            self.fetch_status = f"Partial ({len(self.fetch_errors)} errors)"
        else:
            self.fetch_status = "Complete"
        
        if callback:
            callback(f"Done! {sum(d['action_count'] for d in self.symbol_actions.values())} actions found", 100)
        
        return self.symbol_actions
    
    @staticmethod
    def _same_event(a: Dict, b: Dict) -> bool:
        """Is `b` an action already in the list as `a`?

        NSE and BSE both announce a company's actions, in different words ('Dividend - Rs 7 Per
        Share' / 'Final Dividend - Rs. - 7.0000'), so across the two exchanges the same ex-date
        and type is the same event - except that a final and a special dividend can share an
        ex-date, so dividends must also match on the amount."""
        if a.get('ex_date') != b.get('ex_date'):
            return False
        if a.get('source') == b.get('source'):
            return a.get('purpose', '').lower()[:20] == b.get('purpose', '').lower()[:20]
        if a.get('category') != b.get('category'):
            return False
        if a.get('category') != 'dividend':
            return True
        x, y = a.get('amount') or 0, b.get('amount') or 0
        return x == 0 or y == 0 or abs(x - y) < 0.005

    def get_symbol_summary(self, symbol: str) -> Dict:
        """Get summary for a specific symbol."""
        data = self.symbol_actions.get(symbol, {})
        if not data:
            return {
                'symbol': symbol,
                'total_actions': 0,
                'upcoming': [],
                'past': [],
                'next_event': None,
                'categories': {},
            }
        
        upcoming = data.get('upcoming', [])
        return {
            'symbol': symbol,
            'total_actions': data.get('action_count', 0),
            'upcoming': upcoming,
            'past': data.get('past', []),
            'next_event': upcoming[0] if upcoming else None,
            'categories': data.get('categories', {}),
            'sources': data.get('sources', []),
        }
    
    def format_action_line(self, action: Dict) -> str:
        """Format a single action for display."""
        icon = action.get('icon', '📋')
        cat = action.get('category', 'other')
        purpose = action.get('purpose', 'N/A')
        ex_date = action.get('ex_date', 'N/A')
        days = action.get('days_until')
        amount = action.get('amount', 0)
        source = action.get('source', '')
        
        days_str = ""
        if days is not None:
            if days < 0:
                days_str = f" ({abs(days)}d ago)"
            elif days == 0:
                days_str = " (TODAY)"
            else:
                days_str = f" ({days}d)"
        
        amount_str = f" Rs.{amount:.2f}" if amount > 0 else ""
        
        return f"{icon} {purpose}{amount_str} | Ex: {ex_date}{days_str} [{source}]"
    
    def get_stats(self) -> Dict:
        """Get overall statistics."""
        total_upcoming = sum(d.get('upcoming_count', 0) for d in self.symbol_actions.values())
        total_actions = sum(d.get('action_count', 0) for d in self.symbol_actions.values())
        
        category_counts = {}
        for sym_data in self.symbol_actions.values():
            for cat, acts in sym_data.get('categories', {}).items():
                category_counts[cat] = category_counts.get(cat, 0) + len(acts)
        
        return {
            'total_symbols': len(self.symbol_actions),
            'total_actions': total_actions,
            'total_upcoming': total_upcoming,
            'category_counts': category_counts,
            'fetch_time': self.last_fetch_time,
            'fetch_status': self.fetch_status,
            'errors': self.fetch_errors,
            'sources_used': list(set(
                src for d in self.symbol_actions.values() 
                for src in d.get('sources', [])
            )),
        }
    
    def export_json(self, filepath: str):
        """Export all actions to JSON."""
        data = {
            'generated_at': datetime.now().isoformat(),
            'stats': self.get_stats(),
            'symbols': self.symbol_actions,
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def export_csv(self, filepath: str):
        """Export all actions to CSV."""
        import csv
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Symbol', 'Company', 'Category', 'Purpose', 'Amount',
                'Ex-Date', 'Record Date', 'Days Until', 'Upcoming', 'Source'
            ])
            for sym_data in self.symbol_actions.values():
                for action in sym_data.get('all_actions', []):
                    writer.writerow([
                        action.get('symbol', ''),
                        action.get('company', ''),
                        action.get('category', ''),
                        action.get('purpose', ''),
                        action.get('amount', ''),
                        action.get('ex_date', ''),
                        action.get('record_date', ''),
                        action.get('days_until', ''),
                        action.get('is_upcoming', ''),
                        action.get('source', ''),
                    ])


# ============================================================
# TEST / STANDALONE
# ============================================================

if __name__ == "__main__":
    print("=" * 70)
    print("CORPORATE ACTIONS ENGINE v3.0 - Live Test")
    print("=" * 70)
    
    engine = CorporateActionsEngine()
    
    test_stocks = [
        'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ITC', 'WIPRO',
        'VEDL', 'TATASTEEL', 'SBIN', 'LT', 'BALMLAWRIE', 'GNFC'
    ]
    
    def progress(msg, pct):
        print(f"  [{pct:3d}%] {msg}")
    
    print(f"\nScanning {len(test_stocks)} stocks...")
    results = engine.scan_watchlist(test_stocks, callback=progress)
    
    print(f"\n{'=' * 70}")
    print("RESULTS")
    print("=" * 70)
    
    for symbol in sorted(results.keys()):
        data = results[symbol]
        upcoming = data.get('upcoming', [])
        total = data.get('action_count', 0)
        
        print(f"\n{symbol}: {total} actions, {len(upcoming)} upcoming")
        for action in upcoming[:5]:
            print(f"  {engine.format_action_line(action)}")
    
    stats = engine.get_stats()
    print(f"\n{'=' * 70}")
    print(f"STATISTICS")
    print(f"  Total Symbols: {stats['total_symbols']}")
    print(f"  Total Actions: {stats['total_actions']}")
    print(f"  Upcoming: {stats['total_upcoming']}")
    print(f"  Sources: {stats['sources_used']}")
    print(f"  Categories: {stats['category_counts']}")
    print(f"  Errors: {stats['errors']}")
    print("=" * 70)
