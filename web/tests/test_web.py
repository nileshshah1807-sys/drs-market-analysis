"""Test of the web version's server (runs on this PC, no Vercel needed; prices from Yahoo).

    python web/tests/test_web.py        exit code 0 = everything passed
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
os.environ.pop('VERCEL', None)
os.environ.pop('SECRET_KEY', None)
os.environ.pop('INVITE_CODE', None)
for k in ('KV_REST_API_URL', 'KV_REST_API_TOKEN', 'UPSTASH_REDIS_REST_URL', 'UPSTASH_REDIS_REST_TOKEN', 'DRS_STORE_FILE'):
    os.environ.pop(k, None)
sys.path.insert(0, str(WEB / 'api'))

import index  # noqa: E402
import market_data  # noqa: E402  (the copy in api/_core)
import scoring  # noqa: E402

passed, problems = [], []


def check(label, ok, detail=''):
    (passed if ok else problems).append(f"{'PASS' if ok else 'FAIL'} {label} {detail}".strip())


def strict_json(resp):
    def bad(c):
        raise ValueError(f"not valid JSON: {c}")
    return json.loads(resp.get_data(as_text=True), parse_constant=bad)


def client():
    return index.app.test_client()


# ---- 1. the shared code is the desktop's own ----
import subprocess  # noqa: E402
sync = subprocess.run([sys.executable, str(WEB / 'sync_core.py'), '--check'], capture_output=True, text=True)
check('scoring code is the same as the desktop app', sync.returncode == 0, sync.stdout.strip())

# ---- 2. security ----
c = client()
check('changes must be JSON', c.post('/api/login', data='name=a&password=b').status_code == 415)
check('signed out: no data', c.get('/api/watchlist').status_code == 401 and c.get('/api/me').status_code == 401)
r = c.post('/api/signup', json={'name': 'alice', 'password': 'secret-pass-1', 'invite': 'wrong'})
check('wrong invite code refused', r.status_code == 403)
check('bad user name refused', c.post('/api/signup', json={'name': 'a!', 'password': 'secret-pass-1', 'invite': 'dev'}).status_code == 400)
check('short password refused', c.post('/api/signup', json={'name': 'alice', 'password': 'short', 'invite': 'dev'}).status_code == 400)
r = c.post('/api/signup', json={'name': 'alice', 'password': 'secret-pass-1', 'invite': 'dev'})
cookie = r.headers.get('Set-Cookie', '')
check('sign up', r.status_code == 200 and 'drs_session=' in cookie and 'HttpOnly' in cookie and 'SameSite=Lax' in cookie, cookie[:80])
check('signed in after sign up', c.get('/api/me').get_json() == {'name': 'alice'})
check('user name taken', client().post('/api/signup', json={'name': 'ALICE', 'password': 'secret-pass-2', 'invite': 'dev'}).status_code == 409)
t = client()
t.set_cookie('drs_session', index._make_session('alice')[:-3] + 'abc')
check('forged session refused', t.get('/api/me').status_code == 401)
hacker = client()
codes = [hacker.post('/api/login', json={'name': 'alice', 'password': f'guess-{i}'}).status_code for i in range(index.LOGIN_TRIES + 1)]
check('wrong passwords locked out after 8 tries', codes[:index.LOGIN_TRIES] == [401] * index.LOGIN_TRIES and codes[-1] == 429, str(codes))
check('even the right password waits out the lock', hacker.post('/api/login', json={'name': 'alice', 'password': 'secret-pass-1'}).status_code == 429)
index.store.delete('fail:alice')
b = client()
check('sign in', b.post('/api/login', json={'name': 'Alice', 'password': 'secret-pass-1'}).status_code == 200 and b.get('/api/me').status_code == 200)

# ---- 3. watchlist ----
r = c.put('/api/watchlist', json={'symbols': ['reliance', ' TCS.NS', 'bad sym!', 'M&M', 'reliance', 'INFY.BO', '<script>']})
check('watchlist cleaned', r.get_json()['symbols'] == ['RELIANCE', 'TCS', 'M&M', 'INFY'], str(r.get_json()))
check('watchlist saved', c.get('/api/watchlist').get_json()['symbols'] == ['RELIANCE', 'TCS', 'M&M', 'INFY'])
bob = client()
bob.post('/api/signup', json={'name': 'bob', 'password': 'bobs-password', 'invite': 'dev'})
check("each person has their own watchlist", bob.get('/api/watchlist').get_json()['symbols'] == [])

# ---- 4. scan: the same scores as the desktop app ----
yesterday = (datetime.now(index.IST) - timedelta(days=1)).strftime('%Y-%m-%d')
index.set_json('hist:alice', {yesterday: {'RELIANCE': [12.0, 'STRONG SELL'], 'TCS': [50.0, 'HOLD']}})
t0 = time.time()
r = c.post('/api/scan', json={'symbols': ['RELIANCE', 'TCS', 'INFY', 'ZZNOTREAL1']})
took = time.time() - t0
data = strict_json(r)
syms = [x['symbol'] for x in data['results']]
check('scan', r.status_code == 200 and syms == ['RELIANCE', 'TCS', 'INFY'] and data['failed'] == ['ZZNOTREAL1'],
      f"{syms} failed={data['failed']} in {took:.1f}s")
check('scan answers inside the time limit', took < 45, f"{took:.1f}s")
frames = market_data.load_scan_history(['RELIANCE', 'TCS', 'INFY'], years=2)
same = []
for res in data['results']:
    df = market_data.slice_period(frames[res['symbol']], '2y')
    d = scoring.indicators(df)
    s = scoring.Scorer.score(d)
    tg = scoring.TargetCalc.calc(d, s['rec'])
    same.append(abs(s['total'] - res['score']) < 1e-9 and s['rec'] == res['rec'] and tg['sl'] == res['targets']['sl'] and tg['t2'] == res['targets']['t2'])
check('scores, signals and targets match the desktop calculation', all(same), str(same))
rel = data['results'][0]
check('previous scan compared', rel.get('prev_score') == 12.0 and rel.get('prev_rec') == 'STRONG SELL' and rel.get('prev_date') == yesterday)
check('result has everything the page shows', all(k in rel for k in ('price', 'change', 'rsi', 'breakdown', 'targets', 'st_sig', 'vwap_sig', 'high52',
                                                                    'low52', 'liquidity_cr', 'rs', 'hourly', 'patterns')) and len(rel['breakdown']) == 10)
check('vs Nifty 50 worked out', rel['rs'].get('3M') is not None, str(rel['rs']))
r = c.post('/api/scan', json={'symbols': [f'ZZFAKE{i}' for i in range(15)]})
d2 = r.get_json()
check('at most 10 stocks per call', len(d2['results']) + len(d2['failed']) + len(d2['too_new']) == index.SCAN_BATCH)

# ---- 5. saving the scan, history, last scan ----
r = c.post('/api/scan/save', json={'results': data['results']})
check('scan saved', r.status_code == 200 and r.get_json()['days'] == 2)
last = c.get('/api/scan/last').get_json()
check('last scan shown again', [x['symbol'] for x in last['results']] == syms and last['when'])
pts = c.get('/api/history?symbol=RELIANCE').get_json()['points']
check('score history', len(pts) == 2 and pts[0]['score'] == 12.0, str(pts))
check("other people can't see it", bob.get('/api/scan/last').get_json()['results'] == [])

# ---- 6. chart ----
r = c.get('/api/chart?symbol=RELIANCE&period=6mo')
d = strict_json(r)
check('price chart data', r.status_code == 200 and 100 < len(d['t']) < 140 and len(d['c']) == len(d['t']) == len(d['v']), f"{len(d['t'])} days")
check('bad period refused', c.get('/api/chart?symbol=RELIANCE&period=10y').status_code == 400)
check('unknown stock', c.get('/api/chart?symbol=ZZNOTREAL1&period=1y').status_code == 404)

# ---- 6b. company search: the list the page searches, and the live look-up for new listings ----
listed = json.loads((WEB / 'public' / 'symbols.json').read_text(encoding='utf-8'))['companies']
rel = next((e for e in listed if e[5] == 'RELIANCE'), None)
check('company list shipped with the page', len(listed) > 5000 and all(len(e) == 6 and e[0] and e[5] for e in listed), f"{len(listed)} companies")
check('a company has its full name and both symbols', rel is not None and rel[:4] == ['Reliance Industries Limited', 'RELIANCE', 'RELIANCE', '500325'], str(rel))
check('what gets added is always a usable symbol', all(index.SYMBOL_RE.match(e[5]) for e in listed) and len({e[5] for e in listed}) == len(listed))
check('NSE SME stocks are added the way prices are listed (-SM)', any(e[5] == e[1] + '-SM' for e in listed))
check('live search needs sign-in', client().get('/api/search?q=tata').status_code == 401)
check('live search ignores very short text', c.get('/api/search?q=ta').get_json() == {'companies': []})
found = c.get('/api/search?q=tata capital').get_json()['companies']
check('live search (Yahoo) for companies not in the list', isinstance(found, list) and all(len(e) == 6 and index.SYMBOL_RE.match(e[5]) for e in found)
      and (not found or any('tata' in e[0].lower() for e in found)), str(found[:2]))

# ---- 7. password, sign out ----
check('password change needs the current one', c.post('/api/password', json={'old': 'nope', 'new': 'new-password-1'}).status_code == 403)
check('password changed', c.post('/api/password', json={'old': 'secret-pass-1', 'new': 'new-password-1'}).status_code == 200
      and client().post('/api/login', json={'name': 'alice', 'password': 'new-password-1'}).status_code == 200)
r = c.post('/api/logout', json={})
check('sign out', r.status_code == 200 and c.get('/api/me').status_code == 401)

# ---- 8. what Vercel shows before setup is finished ----
saved_store = index.store
index.store = None
check('says how to connect the database', 'Upstash' in client().get('/api/me').get_json().get('error', ''))
check('health check works without it', client().get('/api/health').get_json()['ok'] is True)
index.store = saved_store
index.ON_VERCEL = True
r = client().get('/api/me')
check('says SECRET_KEY is missing', r.status_code == 503 and 'SECRET_KEY' in r.get_json()['error'])
check('no sign-ups without an invite code on Vercel', client().post('/api/signup', json={'name': 'eve01', 'password': 'whatever-1', 'invite': 'dev'}).status_code in (403, 503))
index.ON_VERCEL = False

# ---- 9. the Upstash database client (against a stand-in for its REST API) ----
fake, calls = {}, []


class FakeResp:
    def __init__(self, result):
        self._r = result
    def raise_for_status(self):
        pass
    def json(self):
        return {'result': self._r}


def fake_post(url, headers=None, json=None, timeout=None):
    calls.append((url, headers, json))
    cmd, *args = json
    if cmd == 'SET':
        fake[args[0]] = args[1]
        return FakeResp('OK')
    if cmd == 'GET':
        return FakeResp(fake.get(args[0]))
    if cmd == 'DEL':
        return FakeResp(int(fake.pop(args[0], None) is not None))
    if cmd == 'INCR':
        fake[args[0]] = str(int(fake.get(args[0], 0)) + 1)
        return FakeResp(int(fake[args[0]]))
    if cmd == 'EXPIRE':
        return FakeResp(1)
    raise AssertionError(cmd)


real_post = index.requests.post
index.requests.post = fake_post
try:
    up = index.UpstashStore('https://example.upstash.io/', 'tok')
    up.set('k', '{"a":1}', ex=60)
    ok = up.get('k') == '{"a":1}' and up.incr('n', 900) == 1 and up.incr('n', 900) == 2
    up.delete('k')
    ok = ok and up.get('k') is None
    check('Upstash client', ok and calls[0] == ('https://example.upstash.io', {'Authorization': 'Bearer tok'}, ['SET', 'k', '{"a":1}', 'EX', '60'])
          and sum(1 for c_ in calls if c_[2][0] == 'EXPIRE') == 1, str(calls[:2]))
finally:
    index.requests.post = real_post

print("\n".join(passed))
print(f"\n==== PROBLEMS: {len(problems)} ====")
print("\n".join(problems) if problems else "none")
sys.exit(1 if problems else 0)
