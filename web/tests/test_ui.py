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


def pdf_text(data_uri, save_as):
    """(number of pages, all the text) of a PDF the page made (given as a data: URI); also keeps the file."""
    import io
    import pdfplumber
    raw = base64.b64decode(data_uri.split(',', 1)[1])
    (SHOTS / save_as).write_bytes(raw)
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        return len(pdf.pages), "\n".join(page.extract_text() or '' for page in pdf.pages), raw[:5]


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
        check('help shows the new signal cut-offs', (await p.js("document.querySelector('#help-signals').textContent")).startswith('62 to 100Strong buy'))
        check('Settings explains the scoring check', '70% of the score' in await p.js("document.querySelector('#score-check').textContent"))

        # the search box: type the first letters of a company's name, pick it from the list
        typing = "(() => { const i=document.querySelector('#add-input'); i.focus(); i.value=%s; i.dispatchEvent(new Event('input',{bubbles:true})); return true; })()"
        options = "[...document.querySelectorAll('#add-list li[role=option]')].map(li => li.innerText.replace(/\\s+/g, ' '))"
        await p.js(typing % "'relia'")
        check('suggestions appear while typing', await p.wait("document.querySelectorAll('#add-list li[role=option]').length >= 3", 20))
        opts = await p.js(options)
        check('a suggestion shows the full name and both exchanges', 'Reliance Industries Limited' in opts[0] and 'NSE RELIANCE' in opts[0]
              and 'BSE RELIANCE' in opts[0] and '500325' in opts[0], opts[0])
        check('typed letters are highlighted', await p.js("document.querySelector('#add-list mark').textContent") == 'Relia')
        await p.shot('01b_suggestions')
        await p.js("document.querySelector('#add-input').dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowDown', bubbles: true})); true")
        check('arrow keys move through the list', await p.js("document.querySelector('#add-list li[aria-selected=true]').id") == 'sg-1')
        await p.js("document.querySelector('#add-input').dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowUp', bubbles: true})); true")
        await p.js("document.querySelector('#add-form').requestSubmit(); true")          # Enter
        check('Enter adds the highlighted company', await p.wait("document.querySelectorAll('#chips .chip').length === 1", 15)
              and 'Reliance Industries Limited' in await p.js("document.querySelector('#chips .chip').innerText"))
        await p.js(typing % "'tata consult'")
        await p.wait("document.querySelectorAll('#add-list li[role=option]').length >= 1", 10)
        check('several words find a company', 'Tata Consultancy Services' in (await p.js(options))[0])
        await p.js("document.querySelector('#add-list li[role=option]').dispatchEvent(new PointerEvent('pointerdown', {bubbles: true})); true")
        check('clicking a suggestion adds it', await p.wait("[...document.querySelectorAll('#chips .chip')].some(c => c.innerText.startsWith('TCS'))", 15))
        await p.js(typing % "'creative cast'")
        await p.wait("document.querySelectorAll('#add-list li[role=option]').length >= 1", 10)
        opts = await p.js(options)
        check('a BSE-only company says so', 'Creative Castings' in opts[0] and 'NSE not listed' in opts[0] and 'BSE CREATIVE' in opts[0], opts[0])
        await p.js(typing % "'eventions'")
        await p.wait("document.querySelectorAll('#add-list li[role=option]').length >= 1", 10)
        check('an NSE SME company is marked', 'SME' in (await p.js(options))[0])
        await p.js(typing % "'relia'")
        await p.wait("document.querySelectorAll('#add-list li[role=option]').length >= 3", 10)
        check('a company already added is marked', 'In your watchlist' in (await p.js(options))[0])
        await p.js(typing % "'zzqqxx'")
        check('nothing found: says so', await p.wait("(document.querySelector('#add-list .note') || {}).textContent?.startsWith('No company found')", 10))
        await p.js(typing % "''")

        # add stocks
        await p.js("""document.querySelector('#bulk').value='RELIANCE, TCS, INFY HDFCBANK\\nITC SBIN ZZNOTREAL1';
            document.querySelector('#bulk-btn').click(); true""")
        check('stocks added', await p.wait("document.querySelectorAll('#chips .chip').length === 7", 15))
        await p.js("document.querySelector('#add-input').value='lt'; document.querySelector('#add-form').requestSubmit(); true")
        check('one stock added', await p.wait("document.querySelectorAll('#chips .chip').length === 8", 15))
        await p.js("document.querySelector('button[data-tab=watchlist]').click(); true")
        await asyncio.sleep(0.5)
        await p.shot('02_watchlist')

        # save the watchlist as a file (the desktop app's formats) ...
        chips = sorted(await p.js("[...document.querySelectorAll('#chips .chip')].map(c => c.querySelector('button').dataset.del)"))
        check('watchlist tab shows the count', await p.js("document.querySelector('#wl-count').textContent") == f"{len(chips)} stocks")
        made = {fmt: json.loads(await p.js("JSON.stringify(watchlistFile('%s'))" % fmt)) for fmt in ('json', 'csv', 'txt')}
        saved = json.loads(made['json']['text'])
        check('save as JSON: the desktop app\'s own format', saved['watchlist'] == chips and 'app' in saved and made['json']['name'].startswith('my_watchlist_20')
              and made['json']['name'].endswith('.json'), made['json']['name'])
        lines = made['csv']['text'].lstrip('\ufeff').strip().splitlines()
        check('save as CSV: symbols with company names, for Excel', made['csv']['text'].startswith('\ufeff') and lines[0] == 'Symbol,Company'
              and 'RELIANCE,Reliance Industries Limited' in lines and len(lines) == len(chips) + 1, str(lines[:3]))
        check('save as text: one symbol per line', made['txt']['text'].split() == chips)
        try:
            await p.send('Browser.setDownloadBehavior', behavior='allow', downloadPath=str(SHOTS))
        except RuntimeError:
            await p.send('Page.setDownloadBehavior', behavior='allow', downloadPath=str(SHOTS))
        await p.js("document.querySelector('#wl-save').click(); true")
        check('Save watchlist button downloads the file', await p.wait("[...document.querySelectorAll('.toast b')].some(b => b.textContent === 'Watchlist saved')", 20))
        got = []
        for _ in range(40):
            got = list(SHOTS.glob('my_watchlist_*.json'))
            if got and got[0].stat().st_size > 20:
                break
            await asyncio.sleep(0.5)
        check('the saved file holds the watchlist', bool(got) and json.loads(got[0].read_text(encoding='utf-8'))['watchlist'] == chips, str([g.name for g in got]))

        # ... and load one back
        load = "(async () => { await loadWatchlistFile(new File([%s], %s)); return [...document.querySelectorAll('.toast b')].pop().textContent; })()"
        csv_text = 'Symbol,Company\r\nRELIANCE,Reliance Industries Limited\r\nwipro,"Wipro, Limited"\r\nnot a symbol!,x\r\n'
        said = await p.js(load % (json.dumps(csv_text), json.dumps('list.csv')))
        chips2 = await p.js("[...document.querySelectorAll('#chips .chip')].map(c => c.querySelector('button').dataset.del)")
        check('load a CSV: only the new stock is added (names and junk ignored)', said == 'Added 1 stock from list.csv' and sorted(chips2) == sorted(chips + ['WIPRO']), f"{said} {chips2}")
        await p.js("document.querySelector('#chips button[data-del=WIPRO]').click(); true")
        await p.wait(f"document.querySelectorAll('#chips .chip').length === {len(chips)}", 10)
        desktop_json = json.dumps({'watchlist': ['tcs', 'INFY.NS'], 'date': '2026-10-13', 'app': "DR. NILESH SHAH'S Analysis"})
        check('load a desktop watchlist file with nothing new', await p.js(load % (json.dumps(desktop_json), json.dumps('my_watchlist.json'))) == 'Nothing new in that file')
        check('a file with no symbols is refused politely', await p.js(load % (json.dumps('hello world!\nthis is not a list\n'), json.dumps('notes.txt'))) == 'No stocks found in that file')
        check('a broken file is refused politely', await p.js(load % (json.dumps('{not json'), json.dumps('bad.json'))) == "Couldn't read that file")
        pick = SHOTS / 'to_load.txt'
        pick.write_text('HCLTECH\n', encoding='utf-8')
        doc = await p.send('DOM.getDocument')
        node = await p.send('DOM.querySelector', nodeId=doc['root']['nodeId'], selector='#wl-file')
        await p.send('DOM.setFileInputFiles', nodeId=node['nodeId'], files=[str(pick)])
        check('Load from file adds the stocks in the chosen file', await p.wait("!!document.querySelector('#chips button[data-del=HCLTECH]')", 15))
        await p.js("document.querySelector('#chips button[data-del=HCLTECH]').click(); true")
        check('watchlist back as it was', await p.wait(f"document.querySelectorAll('#chips .chip').length === {len(chips)}", 10))

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

        # PDF report of the scan: made in the browser, read back here
        uri = await p.js("(async () => (await buildScanPdf()).output('datauristring'))()")
        pages, text, magic = pdf_text(uri, 'scan_report.pdf')
        check('PDF report: a real PDF with the letterhead', magic == b'%PDF-' and "DR. NILESH SHAH'S MARKET ANALYSIS" in text
              and 'Stock technical analysis report' in text and f'Page 1 of {pages}' in text, f"{pages} page(s), {len(uri) // 1024} KB")
        check('PDF report: every scanned stock with its company name, signal, stop-loss and targets',
              all(sym in text for sym in ('RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ITC', 'SBIN', 'LT')) and 'Reliance Industries' in text
              and all(h in text for h in ('Stop-loss', 'Target 1', 'Target 2', 'Risk : reward', 'Signal', 'Average score')))
        check('PDF report: says what was not scored, and carries the disclaimer', 'ZZNOTREAL1' in text and 'not financial advice' in text)
        await p.js("document.querySelector('#f-rec').value = 'HOLD'; document.querySelector('#f-rec').dispatchEvent(new Event('input', {bubbles: true})); true")
        shown = await p.js("[...document.querySelectorAll('#results-box tr[data-sym]')].map(r => r.dataset.sym)")
        uri = await p.js("(async () => (await buildScanPdf()).output('datauristring'))()")
        _, text, _ = pdf_text(uri, 'scan_report_hold_only.pdf')
        body = text.split('Scan results', 1)[-1].split('Score: 62-100', 1)[0]
        hidden = [x for x in ('RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ITC', 'SBIN', 'LT') if x not in shown]
        check('PDF report follows the table filters', bool(shown) and all(x in body for x in shown) and not any(f"\n{x} " in body for x in hidden)
              and 'Showing only: signal HOLD' in text, f"shown {shown}")
        await p.js("document.querySelector('#f-rec').value = 'All'; document.querySelector('#f-rec').dispatchEvent(new Event('input', {bubbles: true})); true")
        try:
            await p.send('Browser.setDownloadBehavior', behavior='allow', downloadPath=str(SHOTS))
        except RuntimeError:
            await p.send('Page.setDownloadBehavior', behavior='allow', downloadPath=str(SHOTS))
        await p.js("document.querySelector('#pdf-btn').click(); true")
        check('PDF report button downloads the file', await p.wait("[...document.querySelectorAll('.toast b')].some(b => b.textContent === 'PDF downloaded')", 30))
        files = []
        for _ in range(40):                      # the browser writes the file a moment after the click
            files = [f.name for f in SHOTS.glob('Market_Analysis_scan_*.pdf')]
            if files and (SHOTS / files[0]).stat().st_size > 1000:
                break
            await asyncio.sleep(0.5)
        check('the downloaded file is named after the scan date', bool(files) and (SHOTS / files[0]).read_bytes()[:5] == b'%PDF-', str(files))

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
        sym = await p.js("state.selected")
        uri = await p.js("(async () => (await buildStockPdf(state.results.find(r => r.symbol === state.selected))).output('datauristring'))()")
        pages, text, magic = pdf_text(uri, 'stock_report.pdf')
        check('stock PDF: score, stop-loss and targets, score parts, patterns', magic == b'%PDF-' and sym in text
              and all(h in text for h in ('Stop-loss and targets', 'Target 3 (aggressive)', 'Risk : reward', 'What makes up the score', 'SuperTrend', 'Patterns', 'vs Nifty 3M')),
              f"{sym}, {pages} page(s)")
        check('stock PDF button is on the details page', await p.js("!!document.querySelector('#d-pdf')"))
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
        await p.js(typing % "'hdfc'")
        await p.wait("document.querySelectorAll('#add-list li[role=option]').length >= 3", 10)
        fits = await p.js("(r => r.left >= 0 && r.right <= window.innerWidth + 1)(document.querySelector('#add-list').getBoundingClientRect())")
        check('phone: the suggestion list fits the screen', fits)
        await p.js("document.querySelector('#add-input').scrollIntoView({block: 'start'}); true")
        await asyncio.sleep(0.4)
        await p.shot('11b_phone_suggestions')
        await p.js(typing % "''")
        await p.js("window.scrollTo(0, 0); true")
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
