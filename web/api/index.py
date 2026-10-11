"""
Web version of DR. NILESH SHAH'S MARKET ANALYSIS - the server (Flask on Vercel).

The scoring, stop-loss/targets and pattern detection are the desktop app's own code (api/_core,
copied from the desktop folder by sync_core.py), so a stock gets the same score on the web as
in the desktop app.

Data is kept in Upstash Redis (free, connected through Vercel > Storage). Without it - running
on this PC with dev_server.py - everything is kept in memory / a local file.

Keys:  user:<name>   account (salt + password hash)
       wl:<name>     the user's watchlist
       hist:<name>   {date: {symbol: [score, signal]}} - last 40 scan days, for "Score Chg"
       scan:<name>   the last scan's results, shown again when the page is reopened
       fail:<name>   failed sign-ins (15-minute window)
"""

import base64
import hashlib
import hmac
import json
import logging
import math
import os
import re
import secrets
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / '_core'))

import numpy as np
import pandas as pd
import requests
from flask import Flask, g, jsonify, request

import market_data
import scoring
from pattern_recognition import PatternDetector
from scoring import NIFTY_SYMBOL, Scorer, TargetCalc, relative_strength, safe_float

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('drs-web')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

IST = timezone(timedelta(hours=5, minutes=30))
ON_VERCEL = bool(os.environ.get('VERCEL'))
COOKIE = 'drs_session'
SESSION_DAYS = 30
NAME_RE = re.compile(r'^[A-Za-z0-9_.-]{3,20}$')
SYMBOL_RE = re.compile(r'^[A-Z0-9][A-Z0-9&_.-]{0,19}$')
MAX_WATCHLIST = 300
SCAN_BATCH = 10           # stocks per /api/scan call: keeps each call well inside Vercel's time limit
HISTORY_DAYS = 40
PERIODS = {'1mo', '3mo', '6mo', '1y', '2y'}
LOGIN_TRIES = 8           # failed sign-ins allowed per 15 minutes


# ============================================================
# STORAGE
# ============================================================

class MemoryStore:
    """Keeps everything in memory (and in `path`, if given) - for running on this PC."""
    kind = 'memory'

    def __init__(self, path=None):
        self.path, self.data, self.lock = path, {}, threading.Lock()
        if path and Path(path).exists():
            try:
                self.data = json.loads(Path(path).read_text(encoding='utf-8'))
            except Exception:
                self.data = {}

    def _save(self):
        if self.path:
            Path(self.path).write_text(json.dumps(self.data), encoding='utf-8')

    def get(self, key):
        with self.lock:
            item = self.data.get(key)
            if item is None:
                return None
            if item[1] and item[1] < time.time():
                del self.data[key]
                return None
            return item[0]

    def set(self, key, value, ex=None):
        with self.lock:
            self.data[key] = [value, time.time() + ex if ex else None]
            self._save()

    def delete(self, key):
        with self.lock:
            self.data.pop(key, None)
            self._save()

    def incr(self, key, ex):
        with self.lock:
            item = self.data.get(key)
            if item is None or (item[1] and item[1] < time.time()):
                item = [0, time.time() + ex]
            item[0] = int(item[0]) + 1
            self.data[key] = item
            self._save()
            return item[0]


class UpstashStore:
    """Upstash Redis over its REST API (what Vercel > Storage > Upstash for Redis creates)."""
    kind = 'upstash'

    def __init__(self, url, token):
        self.url, self.headers = url.rstrip('/'), {'Authorization': f'Bearer {token}'}

    def _cmd(self, *args):
        r = requests.post(self.url, headers=self.headers, json=[str(a) for a in args], timeout=10)
        r.raise_for_status()
        out = r.json()
        if 'error' in out:
            raise RuntimeError(out['error'])
        return out.get('result')

    def get(self, key):
        return self._cmd('GET', key)

    def set(self, key, value, ex=None):
        if ex:
            self._cmd('SET', key, value, 'EX', int(ex))
        else:
            self._cmd('SET', key, value)

    def delete(self, key):
        self._cmd('DEL', key)

    def incr(self, key, ex):
        n = int(self._cmd('INCR', key))
        if n == 1:
            self._cmd('EXPIRE', key, int(ex))
        return n


def make_store():
    url = os.environ.get('KV_REST_API_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')
    token = os.environ.get('KV_REST_API_TOKEN') or os.environ.get('UPSTASH_REDIS_REST_TOKEN')
    if url and token:
        return UpstashStore(url, token)
    if ON_VERCEL:
        return None        # no database connected yet: the API says how to connect one
    return MemoryStore(os.environ.get('DRS_STORE_FILE'))


store = make_store()


def get_json(key, default=None):
    raw = store.get(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def set_json(key, value, ex=None):
    store.set(key, json.dumps(value, separators=(',', ':')), ex)


# ============================================================
# ACCOUNTS AND SESSIONS
# ============================================================

def _secret():
    key = os.environ.get('SECRET_KEY')
    if key:
        return key.encode()
    if ON_VERCEL:
        return None
    if not hasattr(_secret, 'dev'):
        _secret.dev = secrets.token_bytes(32)       # this PC only: sessions end when the server stops
    return _secret.dev


def _hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 200_000).hex()


def _sign(text):
    return hmac.new(_secret(), text.encode(), hashlib.sha256).hexdigest()


def _make_session(name):
    exp = int(time.time()) + SESSION_DAYS * 86400
    body = base64.urlsafe_b64encode(f"{name}|{exp}".encode()).decode()
    return f"{body}.{_sign(body)}"


def _read_session(value):
    try:
        body, sig = value.rsplit('.', 1)
        if not hmac.compare_digest(sig, _sign(body)):
            return None
        name, exp = base64.urlsafe_b64decode(body.encode()).decode().split('|')
        return name if int(exp) > time.time() else None
    except Exception:
        return None


DEV_USER = None   # dev_server.py can sign everyone in as this user (this PC only, for screenshots)


def current_user():
    if DEV_USER and not ON_VERCEL:
        return DEV_USER
    value = request.cookies.get(COOKIE)
    return _read_session(value) if value else None


def _with_cookie(resp, name):
    resp.set_cookie(COOKIE, _make_session(name), max_age=SESSION_DAYS * 86400, httponly=True,
                    secure=ON_VERCEL, samesite='Lax', path='/')
    return resp


def error(message, status=400):
    return jsonify({'error': message}), status


@app.before_request
def guard():
    if not request.path.startswith('/api/') or request.path == '/api/health':
        return None
    if store is None:
        return error("The database isn't connected yet. In Vercel: your project > Storage > "
                     "Create Database > Upstash for Redis > Connect, then redeploy.", 503)
    if _secret() is None:
        return error("SECRET_KEY isn't set. In Vercel: Settings > Environment Variables, then redeploy.", 503)
    # Changes must come as JSON: a form on another website can't send that (no cross-site requests)
    if request.method in ('POST', 'PUT', 'DELETE') and not request.is_json:
        return error("Expected JSON", 415)
    return None


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        g.user = current_user()
        if not g.user:
            return error("Please sign in", 401)
        return fn(*a, **k)
    return wrapper


def _client_ip():
    return (request.headers.get('X-Forwarded-For') or request.remote_addr or '?').split(',')[0].strip()


@app.get('/api/health')
def health():
    return jsonify({'ok': True, 'store': store.kind if store else None, 'secret': _secret() is not None,
                    'signup': bool(os.environ.get('INVITE_CODE')) or not ON_VERCEL,
                    'time': datetime.now(IST).isoformat(timespec='seconds')})


@app.post('/api/signup')
def signup():
    body = request.get_json(silent=True) or {}
    name, password, invite = str(body.get('name', '')).strip(), str(body.get('password', '')), str(body.get('invite', '')).strip()
    code = os.environ.get('INVITE_CODE') or ('dev' if not ON_VERCEL else None)
    if not code:
        return error("New accounts are switched off (no INVITE_CODE set).", 403)
    if store.incr(f"signup:{_client_ip()}", 3600) > 10:
        return error("Too many new accounts from here - try again in an hour.", 429)
    if not hmac.compare_digest(invite.encode(), code.encode()):
        return error("That invite code isn't right. Ask the person who shared the app with you.", 403)
    if not NAME_RE.match(name):
        return error("Choose a user name of 3-20 letters or numbers (also . _ -).")
    if len(password) < 8:
        return error("Choose a password of at least 8 characters.")
    key = f"user:{name.lower()}"
    if store.get(key) is not None:
        return error("That user name is taken - choose another.", 409)
    salt = secrets.token_bytes(16)
    set_json(key, {'name': name, 'salt': salt.hex(), 'hash': _hash(password, salt),
                   'created': datetime.now(IST).isoformat(timespec='seconds')})
    return _with_cookie(jsonify({'name': name}), name)


@app.post('/api/login')
def login():
    body = request.get_json(silent=True) or {}
    name, password = str(body.get('name', '')).strip(), str(body.get('password', ''))
    fail_key = f"fail:{name.lower()}"
    if int(store.get(fail_key) or 0) >= LOGIN_TRIES:
        return error("Too many wrong tries - wait 15 minutes and try again.", 429)
    user = get_json(f"user:{name.lower()}") if NAME_RE.match(name) else None
    if not user or not hmac.compare_digest(_hash(password, bytes.fromhex(user['salt'])), user['hash']):
        store.incr(fail_key, 900)
        return error("Wrong user name or password.", 401)
    store.delete(fail_key)
    return _with_cookie(jsonify({'name': user['name']}), user['name'])


@app.post('/api/logout')
def logout():
    resp = jsonify({'ok': True})
    resp.delete_cookie(COOKIE, path='/')
    return resp


@app.get('/api/me')
@login_required
def me():
    return jsonify({'name': g.user})


@app.post('/api/password')
@login_required
def change_password():
    body = request.get_json(silent=True) or {}
    old, new = str(body.get('old', '')), str(body.get('new', ''))
    key = f"user:{g.user.lower()}"
    user = get_json(key)
    if not user or not hmac.compare_digest(_hash(old, bytes.fromhex(user['salt'])), user['hash']):
        return error("Your current password isn't right.", 403)
    if len(new) < 8:
        return error("Choose a new password of at least 8 characters.")
    salt = secrets.token_bytes(16)
    user.update(salt=salt.hex(), hash=_hash(new, salt))
    set_json(key, user)
    return jsonify({'ok': True})


# ============================================================
# WATCHLIST
# ============================================================

def clean_symbols(items):
    out = []
    for s in items if isinstance(items, list) else []:
        s = str(s).strip().upper().removesuffix('.NS').removesuffix('.BO')
        if SYMBOL_RE.match(s) and s not in out:
            out.append(s)
    return out[:MAX_WATCHLIST]


@app.get('/api/watchlist')
@login_required
def get_watchlist():
    return jsonify({'symbols': get_json(f"wl:{g.user.lower()}", [])})


@app.put('/api/watchlist')
@login_required
def put_watchlist():
    symbols = clean_symbols((request.get_json(silent=True) or {}).get('symbols'))
    set_json(f"wl:{g.user.lower()}", symbols)
    return jsonify({'symbols': symbols})


# ============================================================
# SCAN - the desktop app's scoring, run on a batch of stocks
# ============================================================

_detector = PatternDetector()
_download_lock = threading.Lock()      # yfinance's batch download isn't safe to run twice at once
_nifty = {'df': None, 'at': 0.0}


def jsonable(v):
    """Numbers numpy/pandas hand back -> plain JSON (NaN -> null)."""
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else round(v, 4)
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    return v


def nifty():
    """Nifty 50 history for 'vs Nifty' - fetched at most every 15 minutes."""
    if _nifty['df'] is None or time.time() - _nifty['at'] > 900:
        try:
            with _download_lock:
                df = market_data.load_history([NIFTY_SYMBOL], years=2, exchange='INDEX').get(NIFTY_SYMBOL)
            if df is not None and len(df):
                _nifty.update(df=df, at=time.time())
        except Exception as e:
            logger.warning(f"Nifty 50 download failed: {e}")
    return _nifty['df']


def analyse(symbol, df, days, index_df):
    """One stock's result - the same steps as the desktop app's scan."""
    data = scoring.indicators(df, days)
    try:
        patterns = _detector.detect_all_patterns(df)
    except Exception as e:
        logger.warning(f"Patterns {symbol}: {e}")
        patterns = {'chart': [], 'candlestick': [], 'harmonic': [], 'summary': {}}
    score = Scorer.score(data)
    change = ((data['price'] - data['prev']) / data['prev'] * 100) if data['prev'] > 0 else 0
    targets = TargetCalc.calc(data, score['rec'])
    last_year = df[df.index > df.index[-1] - pd.DateOffset(weeks=52)]
    high52 = float(last_year['High'].max()) if len(last_year) else data['price']
    low52 = float(last_year['Low'].min()) if len(last_year) else data['price']
    return jsonable({
        'symbol': symbol, 'price': data['price'], 'change': change, 'rsi': data['rsi'],
        'score': score['total'], 'rec': score['rec'], 'breakdown': score['breakdown'], 'targets': targets,
        'st_sig': data['supertrend']['sig'], 'vwap_sig': data['vwap']['sig'],
        'high52': high52, 'low52': low52, 'atr': data['atr'], 'liquidity_cr': data['liquidity_cr'],
        'rs': relative_strength(df if days is None else days, index_df),
        'hourly': data['hourly'], 'days': data['days'], 'patterns': patterns,
    })


def _today():
    return datetime.now(IST).strftime('%Y-%m-%d')


def previous_scores(user, symbols):
    """{symbol: (score, signal, date)} from the latest scan day before today."""
    hist, today, out = get_json(f"hist:{user.lower()}", {}), _today(), {}
    for day in sorted((d for d in hist if d < today), reverse=True):
        for s in symbols:
            if s not in out and s in hist[day]:
                out[s] = (hist[day][s][0], hist[day][s][1], day)
    return out


@app.post('/api/scan')
@login_required
def scan():
    symbols = clean_symbols((request.get_json(silent=True) or {}).get('symbols'))[:SCAN_BATCH]
    if not symbols:
        return error("No stocks to scan")
    t0 = time.time()
    days = {}
    try:
        with _download_lock:
            frames = market_data.load_scan_history(symbols, years=2, days=days)
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return error(f"Couldn't download prices ({e}). Try again in a minute.", 502)
    index_df = nifty()
    prev = previous_scores(g.user, symbols)
    results, failed, too_new = [], [], []
    for s in symbols:
        df = frames.get(s)
        if df is None or df.empty:
            failed.append(s)
            continue
        df = market_data.slice_period(df, '2y')
        if len(df) < 20:            # only a new listing's 1-hour candles come this short
            too_new.append(s)
            continue
        try:
            r = analyse(s, df, days.get(s), index_df)
        except Exception as e:
            logger.error(f"Scan {s}: {e}")
            failed.append(s)
            continue
        if s in prev:
            r['prev_score'], r['prev_rec'], r['prev_date'] = prev[s]
        results.append(r)
    logger.info(f"Scan {g.user}: {len(results)}/{len(symbols)} in {time.time() - t0:.1f}s")
    return jsonify({'results': results, 'failed': failed, 'too_new': too_new})


@app.post('/api/scan/save')
@login_required
def save_scan():
    """After the last batch: today's scores go into the history and the results are kept so
    the page can show them again when it's reopened."""
    results = (request.get_json(silent=True) or {}).get('results')
    if not isinstance(results, list) or len(results) > MAX_WATCHLIST:
        return error("Bad results")
    user = g.user.lower()
    hist = get_json(f"hist:{user}", {})
    hist[_today()] = {str(r.get('symbol')): [r.get('score'), r.get('rec')] for r in results if isinstance(r, dict)}
    hist = {d: hist[d] for d in sorted(hist)[-HISTORY_DAYS:]}
    set_json(f"hist:{user}", hist)
    saved = {'when': datetime.now(IST).isoformat(timespec='seconds'), 'results': results}
    if len(json.dumps(saved)) > 900_000:       # Upstash takes up to 1 MB per request
        saved['results'] = [{**r, 'patterns': {}} for r in results]
    set_json(f"scan:{user}", saved)
    return jsonify({'ok': True, 'days': len(hist)})


@app.get('/api/scan/last')
@login_required
def last_scan():
    return jsonify(get_json(f"scan:{g.user.lower()}", {'when': None, 'results': []}))


@app.get('/api/history')
@login_required
def score_history():
    symbol = str(request.args.get('symbol', '')).upper()
    hist = get_json(f"hist:{g.user.lower()}", {})
    return jsonify({'symbol': symbol, 'points': [{'date': d, 'score': hist[d][symbol][0], 'rec': hist[d][symbol][1]}
                                                 for d in sorted(hist) if symbol in hist[d]]})


@app.get('/api/chart')
@login_required
def chart():
    symbol = str(request.args.get('symbol', '')).strip().upper()
    period = str(request.args.get('period', '6mo'))
    if not SYMBOL_RE.match(symbol) or period not in PERIODS:
        return error("Bad symbol or period")
    try:
        with _download_lock:
            df = market_data.load_scan_history([symbol], years=2).get(symbol)
    except Exception as e:
        return error(f"Couldn't download prices ({e})", 502)
    if df is None or len(df) < 2:
        return error(f"No price data for {symbol}", 404)
    hourly = market_data.is_hourly(df)
    if not hourly:
        df = market_data.slice_period(df, period)
    return jsonify(jsonable({
        'symbol': symbol, 'period': period, 'hourly': hourly,
        't': [ts.strftime('%Y-%m-%d %H:%M' if hourly else '%Y-%m-%d') for ts in df.index],
        'o': df['Open'].tolist(), 'h': df['High'].tolist(), 'l': df['Low'].tolist(),
        'c': df['Close'].tolist(), 'v': df['Volume'].tolist(),
    }))


# ============================================================
# THIS PC ONLY: serve the page too (Vercel serves public/ itself)
# ============================================================

if not ON_VERCEL and os.environ.get('DRS_DEV'):
    from flask import send_from_directory
    PUBLIC = HERE.parent / 'public'

    @app.get('/')
    def index_page():
        return send_from_directory(PUBLIC, 'index.html')

    @app.get('/<path:path>')
    def static_files(path):
        return send_from_directory(PUBLIC, path)
