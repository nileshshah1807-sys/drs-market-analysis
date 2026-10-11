"""End-to-end test of the web page in a real browser (Microsoft Edge, headless), on this PC.

    python web/tests/test_ui.py [screenshot folder]

To check the live website instead of a local copy, set DRS_UI_URL (and DRS_UI_INVITE, DRS_UI_USER).

Starts the local server, signs up, adds stocks, scans, opens a stock, the price chart and the
3D map, switches to dark mode and to a phone-sized screen. Any JavaScript error is a failure.
Exit code 0 = everything passed.
"""
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

WEB = Path(__file__).resolve().parents[1]
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / 'drs_web_ui'
SHOTS.mkdir(parents=True, exist_ok=True)
PORT, DEBUG_PORT = 8765, 9333
LIVE = os.environ.get('DRS_UI_URL', '').rstrip('/')
BASE = LIVE or f"http://127.0.0.1:{PORT}"
INVITE, USER = os.environ.get('DRS_UI_INVITE', 'dev'), os.environ.get('DRS_UI_USER', 'tester')
EDGE = next((p for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                         r"C:\Program Files\Microsoft\Edge\Application\msedge.exe") if Path(p).exists()), None)
passed, problems, js_errors = [], [], []


def check(label, ok, detail=''):
    (passed if ok else problems).append(f"{'PASS' if ok else 'FAIL'} {label} {detail}".strip())


class Page:
    def __init__(self, ws):
        self.ws, self.n, self.pending = ws, 0, {}
        self.reader = asyncio.create_task(self._read())

    async def _read(self):
        async for raw in self.ws:
            msg = json.loads(raw)
            if 'id' in msg and msg['id'] in self.pending:
                self.pending.pop(msg['id']).set_result(msg)
            elif msg.get('method') == 'Runtime.exceptionThrown':
                d = msg['params']['exceptionDetails']
                js_errors.append(f"exception: {d.get('exception', {}).get('description') or d.get('text')}"[:300])
            elif msg.get('method') == 'Runtime.consoleAPICalled' and msg['params']['type'] == 'error':
                js_errors.append('console.error: ' + ' '.join(str(a.get('value', a.get('description', ''))) for a in msg['params']['args'])[:300])

    async def send(self, method, **params):
        self.n += 1
        fut = asyncio.get_running_loop().create_future()
        self.pending[self.n] = fut
        await self.ws.send(json.dumps({'id': self.n, 'method': method, 'params': params}))
        msg = await asyncio.wait_for(fut, 60)
        if 'error' in msg:
            raise RuntimeError(f"{method}: {msg['error']}")
        return msg.get('result', {})

    async def js(self, expr):
        r = await self.send('Runtime.evaluate', expression=expr, awaitPromise=True, returnByValue=True)
        if 'exceptionDetails' in r:
            raise RuntimeError(f"JS failed: {expr[:80]}: {r['exceptionDetails'].get('text')}")
        return r.get('result', {}).get('value')

    async def wait(self, expr, timeout=30, step=0.25):
        end = time.time() + timeout
        while time.time() < end:
            if await self.js(expr):
                return True
            await asyncio.sleep(step)
        return False

    async def shot(self, name):
        data = (await self.send('Page.captureScreenshot', format='png'))['data']
        (SHOTS / f"{name}.png").write_bytes(base64.b64decode(data))


async def run():
    info = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version").read())
    req = urllib.request.Request(f"http://127.0.0.1:{DEBUG_PORT}/json/new?about:blank", method='PUT')
    target = json.loads(urllib.request.urlopen(req).read())
    async with websockets.connect(target['webSocketDebuggerUrl'], max_size=100_000_000) as ws:
        p = Page(ws)
        for m in ('Runtime.enable', 'Page.enable'):
            await p.send(m)
        await p.send('Emulation.setDeviceMetricsOverride', width=1400, height=1000, deviceScaleFactor=1, mobile=False)
        await p.send('Page.navigate', url=f"{BASE}/")
        check('sign-in page shown', await p.wait("!document.querySelector('#login').classList.contains('hidden')", 15))
        await p.shot('01_signin')

        # sign up
        await p.js("""document.querySelector('#mode-new').click();
            document.querySelector('#l-name').value=%s; document.querySelector('#l-pass').value='tester-pass-1';
            document.querySelector('#l-invite').value=%s; document.querySelector('#login-form').requestSubmit(); true""" % (json.dumps(USER), json.dumps(INVITE)))
        check('signed up and in', await p.wait("!document.querySelector('#app').classList.contains('hidden')", 20))
        check('starts in light mode', await p.js("document.documentElement.dataset.theme") == 'light')

        # add stocks
        await p.js("""document.querySelector('#bulk').value='RELIANCE, TCS, INFY HDFCBANK\\nITC SBIN ZZNOTREAL1';
            document.querySelector('#bulk-btn').click(); true""")
        check('stocks added', await p.wait("document.querySelectorAll('#chips .chip').length === 7", 15))
        await p.js("document.querySelector('#add-input').value='lt'; document.querySelector('#add-form').requestSubmit(); true")
        check('one stock added', await p.wait("document.querySelectorAll('#chips .chip').length === 8", 15))
        await p.js("document.querySelector('button[data-tab=watchlist]').click(); true")
        await asyncio.sleep(0.5)
        await p.shot('02_watchlist')

        # scan
        await p.js("document.querySelector('#scan-btn').click(); true")
        ok = await p.wait("document.querySelector('#status').textContent === 'Complete'", 150, 0.5)
        rows = await p.js("document.querySelectorAll('#results-box tr[data-sym]').length")
        errs = await p.js("[...document.querySelectorAll('#results-box tr.err')].map(r => r.textContent)")
        check('scan finished', ok and rows == 7 and len(errs) == 1 and 'ZZNOTREAL1' in errs[0], f"{rows} rows, errors {errs}")
        check('summary card counts', await p.wait("document.querySelector('#sum-n') && document.querySelector('#sum-n').textContent === '7'", 5))
        check('scan message slid in', await p.js("[...document.querySelectorAll('.toast b')].some(b => b.textContent.startsWith('Scan complete: 7'))"))
        await asyncio.sleep(1.2)
        await p.shot('03_results_light')

        # sorting
        await p.js("document.querySelector('th[data-sort=score]').click(); true")
        scores = await p.js("[...document.querySelectorAll('#results-box tr[data-sym]')].map(r => parseFloat(r.children[6].textContent))")
        check('sort by score', scores == sorted(scores), str(scores))

        # details
        await p.js("document.querySelector('#results-box tr[data-sym]').click(); true")
        check('stock details', await p.wait("document.querySelector('#p-details .ring') && !document.querySelector('#p-details').hidden", 10))
        await asyncio.sleep(1.5)
        ring = await p.js("document.querySelector('#p-details .ring-num').textContent")
        bars = await p.js("[...document.querySelectorAll('#p-details .track i')].map(i => i.style.width)")
        check('score ring and bars animated to their values', ring not in ('0.0', '') and len(bars) == 10 and all(b.endswith('%') for b in bars), f"{ring} {bars[:3]}")
        check('price ladder drawn', await p.js("document.querySelectorAll('#ladder circle').length") == 4)
        await p.shot('04_details_light')
        await p.js("window.scrollTo(0, document.body.scrollHeight); true")
        await asyncio.sleep(0.4)
        await p.shot('05_details_light_bottom')
        await p.js("window.scrollTo(0, 0); true")

        # price chart and 3D map (chart library from the internet)
        await p.js("document.querySelector('#d-chart').click(); true")
        check('price chart', await p.wait("!!document.querySelector('#chart .main-svg')", 45, 0.5))
        await asyncio.sleep(1.2)
        await p.shot('06_chart_light')
        await p.js("document.querySelector('#c-map').click(); true")
        check('3D market map', await p.wait("!!document.querySelector('#chart .gl-container, #chart canvas')", 30, 0.5))
        await asyncio.sleep(2.0)
        eye1 = await p.js("JSON.stringify(document.querySelector('#chart')._fullLayout.scene.camera.eye)")
        await asyncio.sleep(1.0)
        eye2 = await p.js("JSON.stringify(document.querySelector('#chart')._fullLayout.scene.camera.eye)")
        check('3D map turns by itself', eye1 != eye2, f"{eye1} -> {eye2}")
        await p.shot('07_map_light')

        # dark mode
        await p.js("document.querySelector('#theme-btn').click(); true")
        check('dark mode', await p.wait("document.documentElement.dataset.theme === 'dark'", 5))
        await asyncio.sleep(1.5)
        await p.shot('08_map_dark')
        await p.js("document.querySelector('button[data-tab=results]').click(); true")
        await asyncio.sleep(0.5)
        await p.shot('09_results_dark')
        await p.js("document.querySelector('#results-box tr[data-sym]').click(); true")
        await asyncio.sleep(1.5)
        await p.shot('10_details_dark')

        # reload: still signed in, last scan and dark mode kept
        await p.send('Page.reload')
        check('reload keeps sign-in and last scan', await p.wait("document.querySelectorAll('#results-box tr[data-sym]').length === 7", 20))
        check('reload keeps dark mode', await p.js("document.documentElement.dataset.theme") == 'dark')

        # phone
        await p.send('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=2, mobile=True)
        await p.js("document.querySelector('#theme-btn').click(); true")
        await asyncio.sleep(1.0)
        wide = await p.js("document.documentElement.scrollWidth > window.innerWidth + 1")
        check('phone: no sideways scrolling of the page', not wide)
        await p.shot('11_phone_results')
        await p.js("document.querySelector('#results-box tr[data-sym]').click(); true")
        await asyncio.sleep(1.5)
        await p.shot('12_phone_details')

        # sign out
        await p.js("document.querySelector('#logout-btn').click(); true")
        check('sign out', await p.wait("!document.querySelector('#login').classList.contains('hidden')", 10))
        p.reader.cancel()


def main():
    if not EDGE:
        print("Microsoft Edge not found - UI test skipped")
        return 0
    tmp = Path(tempfile.mkdtemp(prefix='drs_ui_'))
    env = dict(os.environ, PORT=str(PORT), DRS_STORE_FILE=str(tmp / 'store.json'), PYTHONIOENCODING='utf-8')
    env.pop('DRS_DEV_USER', None)
    server = None if LIVE else subprocess.Popen([sys.executable, str(WEB / 'dev_server.py')], env=env,
                                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    edge = subprocess.Popen([EDGE, '--headless=new', f'--remote-debugging-port={DEBUG_PORT}', f'--user-data-dir={tmp / "edge"}',
                             '--no-first-run', '--disable-extensions', '--window-size=1400,1000', 'about:blank'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"{BASE}/api/health", timeout=10)
                urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        asyncio.run(run())
    except Exception as e:
        problems.append(f"CRASHED: {type(e).__name__}: {e}")
    finally:
        edge.terminate()
        if server:
            server.terminate()
        time.sleep(1)
        shutil.rmtree(tmp, ignore_errors=True)
    check('no JavaScript errors', not js_errors, ' | '.join(js_errors[:5]))
    print("\n".join(passed))
    print(f"\nscreenshots: {SHOTS}")
    print(f"==== PROBLEMS: {len(problems)} ====")
    print("\n".join(problems) if problems else "none")
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
