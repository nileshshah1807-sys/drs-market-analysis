"""Deep end-to-end test of DR. NILESH SHAH'S MARKET ANALYSIS.

Don't run this file directly - use run_tests.bat or tests/run_deep_test.py, which run it inside
a throwaway copy of the app. Nothing real is touched:
  - email goes to a fake mail server (nothing is sent)
  - Windows Task Scheduler calls are faked (your real scheduled task isn't changed)
  - dialogs are answered automatically, file dialogs point into the test folder
  - the email password is a dummy kept under a throwaway Credential Manager entry

Every feature is exercised and every error is recorded - including ones the app would
normally hide (logged errors, exceptions in background threads and Tk callbacks).
"""
import os, sys, time, json, csv, logging, threading, traceback, smtplib
from datetime import datetime, timedelta

sys.path.insert(0, os.getcwd())
OUT = os.path.join(os.getcwd(), '_test_out')
os.makedirs(OUT, exist_ok=True)

problems, passed, expected_warnings = [], [], []


# ---------- capture everything that goes wrong ----------
class ErrCapture(logging.Handler):
    def emit(self, record):
        msg = record.getMessage()
        if record.levelno >= logging.ERROR:
            problems.append(f"LOGGED ERROR: {msg[:200]}")


logging.getLogger().addHandler(ErrCapture())
threading.excepthook = lambda a: problems.append(
    f"THREAD EXCEPTION: {a.exc_type.__name__}: {a.exc_value}\n{''.join(traceback.format_tb(a.exc_traceback))[-600:]}")

# ---------- fake mail server ----------
sent = []


class FakeSMTP:
    def __init__(self, *a, **k): pass
    def ehlo(self): pass
    def starttls(self): pass
    def login(self, u, p): pass
    def send_message(self, msg): sent.append(msg)
    def quit(self): pass


smtplib.SMTP = smtplib.SMTP_SSL = FakeSMTP

import keyring
import daily_report
TEST_SERVICE = 'ZZ DR Nilesh Shah deep test - safe to delete'
daily_report.KEYRING_SERVICE = TEST_SERVICE
SENDER = json.load(open('email_config.json'))['sender_email']
keyring.set_password(TEST_SERVICE, SENDER, 'dummy-password-for-test')

import scheduled_report
_fake_task = {'on': False}
scheduled_report.install_task = lambda h, m: (True, f"(test) installed {h:02d}:{m:02d}")
scheduled_report.remove_task = lambda: (True, "(test) removed")
scheduled_report.task_status = lambda: "(test) next run" if _fake_task['on'] else None

import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import dr_shah_analysis as m
import score_history

dialog_log = []


def _info(title, msg, **k):
    dialog_log.append(('info', title, str(msg)))


def _warn(title, msg, **k):
    dialog_log.append(('warn', title, str(msg)))
    if expected_warnings:
        expected_warnings.pop()
    else:
        problems.append(f"UNEXPECTED WARNING DIALOG: {title}: {str(msg)[:160]}")


def _err(title, msg, **k):
    dialog_log.append(('error', title, str(msg)))
    problems.append(f"ERROR DIALOG: {title}: {str(msg)[:200]}")


messagebox.showinfo, messagebox.showwarning, messagebox.showerror = _info, _warn, _err
answers = {'askyesno': True, 'askyesnocancel': True}
messagebox.askyesno = lambda *a, **k: answers['askyesno']
messagebox.askyesnocancel = lambda *a, **k: answers['askyesnocancel']
simpledialog.askstring = lambda *a, **k: 'TestGroup'
paths = {'open': None, 'save': None}
filedialog.askopenfilename = lambda *a, **k: paths['open']
filedialog.asksaveasfilename = lambda *a, **k: paths['save']

root = tk.Tk()
root.report_callback_exception = lambda et, ev, tb: problems.append(
    f"TK CALLBACK EXCEPTION: {et.__name__}: {ev}\n{''.join(traceback.format_tb(tb))[-700:]}")
app = m.App(root)
COLS = list(app.tree['columns'])


def col(name):
    return COLS.index(name)


def cell(item, name):
    return str(app.tree.item(item)['values'][col(name)])


def wait(cond, timeout):          # use as:  yield wait(lambda: ..., seconds)
    return (cond, timeout)


def descendants(w):
    for c in w.winfo_children():
        yield c
        yield from descendants(c)


def close_toplevels():
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            w.destroy()


def check(label, ok, detail=''):
    (passed if ok else problems).append(f"{'PASS' if ok else 'FAIL'} {label} {detail}".strip())


def is_number(text):
    try:
        float(str(text).replace('%', '').replace('+', '').replace(',', '').split()[0])
        return True
    except (ValueError, IndexError):
        return False


# ---------------- steps ----------------
def s_startup():
    tabs = [app.nb.tab(t, 'text').strip() for t in app.nb.tabs()]
    check('all tabs built', len(tabs) == 11, str(tabs))
    check('results table has new columns', 'vs Nifty 3M' in COLS and 'Score Chg' in COLS and 'Candle' in COLS, str(COLS))
    yield wait(lambda: 'checking' not in app.task_status_lbl.cget('text'), 5)


def s_single_instance():
    first = m.single_instance_lock()          # main() isn't used by the test, so nothing holds it yet
    second = m.single_instance_lock()
    check('one copy at a time (second copy refused)', first is not None and second is None)
    yield None


def s_watchlist():
    orig = list(app.watchlist)
    app.entry.insert(0, 'm&m')
    app.add_stock()
    check('add stock (M&M)', 'M&M' in app.watchlist)
    rows = list(app.wl_list.get(0, tk.END))
    app.wl_list.selection_clear(0, tk.END)
    app.wl_list.selection_set(next(i for i, r in enumerate(rows) if app._wl_symbol(r) == 'M&M'))
    app.del_stock()
    check('delete stock', 'M&M' not in app.watchlist)
    app._create_group()
    check('create group', 'TestGroup' in app.watchlist_groups and app.group_var.get() == 'All Stocks')
    app._ask_group = lambda stock: 'TestGroup'            # the "which group?" dialog's answer
    app.wl_list.selection_clear(0, tk.END)
    app.wl_list.selection_set(0)
    first = app._wl_symbol(app.wl_list.get(0))
    app._add_to_group()
    check('add to group', first in app.watchlist_groups['TestGroup'])
    app.group_var.set('TestGroup')
    app._switch_group()
    check('switch group', app.wl_list.size() == 1, f"rows={app.wl_list.size()}")
    app.wl_list.selection_set(0)
    app._remove_from_group()
    check('remove from group', first not in app.watchlist_groups['TestGroup'])
    app.group_var.set('All Stocks')
    app._switch_group()
    for sector in ['Banking', 'IT', 'All']:
        app.sector_var.set(sector)
        app.refresh_watchlist()
    check('watchlist unchanged after ops', sorted(app.watchlist) == sorted(orig))
    yield None


def s_import_save_lists():
    orig = list(app.watchlist)
    files = {}
    files['csv'] = os.path.join(OUT, 'imp.csv')
    open(files['csv'], 'w').write("M&M\n20MICRONS\nBAJAJ-AUTO\n")
    files['txt'] = os.path.join(OUT, 'imp.txt')
    open(files['txt'], 'w').write("TCS\nINFY\n\n")
    files['json'] = os.path.join(OUT, 'imp.json')
    json.dump({'watchlist': ['HDFCBANK', 'ITC']}, open(files['json'], 'w'))
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws['A1'], ws['A2'], ws['A3'], ws['B2'] = 'Symbol', 'SBIN', '20MICRONS', 'M&M'
    files['xlsx'] = os.path.join(OUT, 'imp.xlsx')
    wb.save(files['xlsx'])
    from reportlab.pdfgen import canvas
    files['pdf'] = os.path.join(OUT, 'imp.pdf')
    c = canvas.Canvas(files['pdf'])
    c.drawString(100, 750, "WIPRO LT M&M BAJAJ-AUTO")
    c.save()
    expect = {'csv': {'M&M', '20MICRONS', 'BAJAJ-AUTO'}, 'txt': {'TCS', 'INFY'}, 'json': {'HDFCBANK', 'ITC'},
              'xlsx': {'SBIN', '20MICRONS', 'M&M'}, 'pdf': {'WIPRO', 'LT', 'M&M', 'BAJAJ-AUTO'}}
    for kind, fp in files.items():
        app.watchlist = []
        paths['open'] = fp
        app.import_list()
        check(f'import {kind}', expect[kind] == set(app.watchlist), f"got {sorted(app.watchlist)}")
    app.watchlist = orig
    app.refresh_watchlist()
    for ext in ('json', 'csv', 'txt'):
        paths['save'] = os.path.join(OUT, f'saved.{ext}')
        app.save_list()
        check(f'save list .{ext}', os.path.getsize(paths['save']) > 0)
    yield None


def s_scan():
    t0 = time.time()
    app.start_scan()
    yield wait(lambda: not app.scanning, 400)
    check('scan', len(app.results) >= len(app.watchlist) - 3, f"{len(app.results)}/{len(app.watchlist)} in {time.time()-t0:.0f}s")
    missing = sorted(set(app.watchlist) - {r['symbol'] for r in app.results})
    passed.append(f"INFO symbols with no data: {missing}")
    rs_ok = sum(1 for r in app.results if (r.get('rs') or {}).get('3M') is not None)
    check('relative strength vs Nifty', rs_ok >= 0.9 * len(app.results), f"{rs_ok}/{len(app.results)} stocks have a 3M figure")
    rows = score_history._read()
    today = datetime.now().strftime('%Y-%m-%d')
    check('score history saved', sum(1 for r in rows if r['date'] == today) == len(app.results), f"{len(rows)} rows")


def s_history_compare():
    """Pretend today's scan happened yesterday with one different signal, then scan again."""
    rows = score_history._read()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    target = app.results[0]['symbol']
    for row in rows:
        row['date'] = yesterday
        if row['symbol'] == target:
            row['rec'] = 'STRONG SELL' if row['rec'] != 'STRONG SELL' else 'STRONG BUY'
            row['score'] = '5.0' if row['rec'] == 'STRONG SELL' else '95.0'
    with open(score_history.HISTORY_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=score_history.FIELDS)
        w.writeheader()
        w.writerows(rows)
    app.last_toast = None
    app.start_scan()
    yield wait(lambda: not app.scanning, 400)
    chg = [cell(i, 'Score Chg') for i in app.tree.get_children() if not cell(i, 'Recommendation').startswith('Error')]
    check('Score Chg vs previous day', sum(is_number(v) for v in chg) >= 0.9 * len(chg), f"{chg[:5]}")
    msg = app.last_toast[1] if app.last_toast else ''
    check('signal changes listed after scan', 'Signal changes' in msg and target in msg,
          msg[:150].replace('\n', ' | ') if msg else 'no message after the scan')
    r = next(x for x in app.results if x['symbol'] == target)
    app.update_breakdown(r)
    root.update()

    boxes = [w for w in app.bd_frame.winfo_children()
             if any(c.winfo_class() == 'Label' and c.cget('text') == 'Score history' for c in w.winfo_children())]
    check('score history chart', bool(boxes) and any(c.winfo_class() == 'Canvas' for c in boxes[0].winfo_children()))


def s_results_table():
    n = len(app.tree.get_children())
    for rec in ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL", "All"]:
        app.result_filter_var.set(rec)
        app.filter_results()
    app.search_var.set(app.results[0]['symbol'][:3])
    root.update()
    app.search_var.set('')
    root.update()
    app.hide_illiquid_var.set(True)
    app.filter_results()
    app.hide_illiquid_var.set(False)
    app.filter_results()
    for c in COLS:
        app.sort_tree(c)
        app.sort_tree(c)
    app._sort_col = None
    app.sort_tree('Price')                    # ascending: numbers in order, any 'N/A' rows last
    prices = [cell(i, 'Price') for i in app.tree.get_children()]
    nums = [float(p.replace(',', '')) for p in prices if is_number(p)]   # prices show with thousands commas
    check('numeric sort (text last)', nums == sorted(nums) and all(is_number(p) for p in prices[:len(nums)]))
    check('results filter/search/sort', len(app.tree.get_children()) == n)
    yield None


def s_details_every_stock():
    bad = []
    for r in app.results:
        try:
            app.update_breakdown(r)
            app.update_targets(r)
            app.update_patterns(r)
        except Exception as e:
            bad.append(f"{r['symbol']}: {type(e).__name__}: {e}")
    check('details tabs for every stock', not bad, str(bad[:3]))
    yield None


def s_exports():
    for name, fn, ext in [('excel', app.export_results, 'xlsx'), ('csv', app.export_results, 'csv'),
                          ('pdf', app.export_pdf, 'pdf')]:
        paths['save'] = os.path.join(OUT, f'results.{ext}')
        fn()
        check(f'export {name}', os.path.exists(paths['save']) and os.path.getsize(paths['save']) > 500)
    from openpyxl import load_workbook
    ws = load_workbook(os.path.join(OUT, 'results.xlsx')).active
    check('excel content', ws.max_row == len(app.results) + 1 and ws.cell(1, 12).value == 'Liquidity'
          and ws.cell(1, 14).value == 'vs Nifty 3M (%)', f"rows={ws.max_row}")
    yield None


def s_sector():
    app.analyze_sectors()
    yield wait(lambda: not getattr(app, '_sector_busy', False), 120)
    rows = [app.sector_tree.item(i)['values'] for i in app.sector_tree.get_children()]
    other = next((r[1] for r in rows if r[0] == 'Other'), 0)
    check('sector analysis', len(rows) >= 3 and other <= max(3, len(app.results) // 10),
          f"{len(rows)} sectors, 'Other'={other}")


def s_charts():
    app.tree.selection_set(app.tree.get_children()[0])
    for period in ['1mo', '3mo', '6mo', '1y', '2y']:
        app.chart_period_var.set(period)
        app.show_stock_chart()
        yield wait(lambda: any(w.winfo_class() == 'Canvas' for w in app.chart_frame.winfo_children()), 60)
        check(f'chart {period}', any(w.winfo_class() == 'Canvas' for w in app.chart_frame.winfo_children()))


def s_corporate():
    app.load_corporate_actions()
    yield wait(lambda: app.corp_status.cget('text').startswith(('Done', 'Error', 'Loaded')), 300)
    check('corporate scan', app.corp_status.cget('text').startswith('Done'), app.corp_status.cget('text')[:90])
    for f in ["All", "Upcoming", "Past", "Dividends", "Splits", "Bonus", "Rights", "Buyback", "All"]:
        app.corp_filter_var.set(f)
        app._filter_corporate_actions()
    for i in range(min(5, app.corp_listbox.size())):
        app.corp_listbox.selection_clear(0, tk.END)
        app.corp_listbox.selection_set(i)
        app.show_corporate_popup()
    close_toplevels()
    paths['save'] = os.path.join(OUT, 'corp.csv')
    app.export_corporate_csv()
    check('corporate CSV', os.path.exists(paths['save']))
    yield None


def s_backtest():
    for horizon, liquid in [('10 days', False), ('5 days', False), ('20 days', True)]:
        app.bt_horizon_var.set(horizon)
        app.bt_liquid_var.set(liquid)
        app._bt_result = None
        app.run_backtest()
        yield wait(lambda: str(app.bt_run_btn.cget('state')) == 'normal'
                   and (app._bt_result is not None or 'failed' in app.bt_status.cget('text')), 300)
        check(f'backtest {horizon} liquid={liquid}', app._bt_result is not None and len(app.bt_ind_tree.get_children()) == 10,
              app.bt_status.cget('text')[:80])
    app.bt_liquid_var.set(False)
    app.bt_horizon_var.set('10 days')
    app.run_backtest()
    yield wait(lambda: str(app.bt_run_btn.cget('state')) == 'normal' and app._bt_result is not None, 300)
    if app._bt_result and app._bt_result.get('suggested_weights'):
        suggested = dict(app._bt_result['suggested_weights'])
        app.apply_suggested_weights()
        yield wait(lambda: str(app.bt_run_btn.cget('state')) == 'normal', 120)
        meta = app._weights_meta()
        check('apply suggested weights (+ re-check record)', m.Scorer.WEIGHTS == suggested and meta.get('source') == 'backtest'
              and meta.get('horizon') == 10, str(meta)[:120])
        check('weights status line', 'SUGGESTED' in app.bt_weights_lbl.cget('text'), app.bt_weights_lbl.cget('text')[:90])
        app.recheck_weights()
        yield wait(lambda: not getattr(app, '_recheck_running', False), 300)
        meta = app._weights_meta()
        check('re-check weights', (meta.get('last_result') or {}).get('verdict') in ('ok', 'worse')
              and 'Re-check' in app.bt_weights_lbl.cget('text'), app.bt_weights_lbl.cget('text')[:120])
        app.reset_weights()
        check('reset weights', m.Scorer.WEIGHTS == m.Scorer.DEFAULT_WEIGHTS and app._weights_meta().get('source') == 'default')


def s_settings():
    app.save_email_config()
    check('save email config', daily_report.EmailConfig().is_configured)
    n = len(sent)
    app.test_email()
    check('test email (fake mail server)', len(sent) == n + 1)
    app.save_schedule()
    app.install_windows_task()
    _fake_task['on'] = True
    app._update_task_status()
    check('install task (faked)', 'INSTALLED' in app.task_status_lbl.cget('text'))
    app.remove_windows_task()
    _fake_task['on'] = False
    app.min_liquidity_var.set('1')
    app.save_liquidity_setting()
    expected_warnings.append(1)                # weights not totalling 100 must be refused
    app.weight_vars['rsi'].set(99)
    app.apply_weights()
    app.reset_weights()
    check('weights reset after invalid', m.Scorer.WEIGHTS == m.Scorer.DEFAULT_WEIGHTS)
    yield None


def s_reports():
    answers['askyesnocancel'] = False          # Indian market only
    app.generate_daily_report()
    yield wait(lambda: 'generated' in app.status_lbl.cget('text') or 'failed' in app.status_lbl.cget('text'), 400)
    check('daily report', 'generated' in app.status_lbl.cget('text'), app.status_lbl.cget('text'))
    n = len(sent)
    answers['askyesnocancel'] = True           # watchlist email
    app.send_email_report()
    yield wait(lambda: len(sent) > n or 'failed' in app.status_lbl.cget('text'), 200)
    ok = len(sent) > n and any(p.get_filename() for p in sent[-1].walk())
    html = sent[-1].get_payload()[0].get_payload(decode=True).decode('utf-8', 'ignore') if len(sent) > n else ''
    check('watchlist email (fake mail server)', ok and 'vs Nifty 3M' in html and 'Signal Changes' in html,
          app.status_lbl.cget('text'))
    n = len(sent)
    answers['askyesnocancel'] = False          # full market email
    app.send_email_report()
    yield wait(lambda: len(sent) > n or 'failed' in app.status_lbl.cget('text') or 'Error' in app.status_lbl.cget('text'), 500)
    check('full market email (fake mail server)', len(sent) > n, app.status_lbl.cget('text'))


def s_auto_report():
    now = time.localtime()
    json.dump({'enabled': True, 'hour': now.tm_hour, 'minute': now.tm_min, 'report_type': 'Indian Only'},
              open(m.SCHEDULE_FILE, 'w'))
    if os.path.exists(scheduled_report.STATE_FILE):
        os.remove(scheduled_report.STATE_FILE)
    n = len(sent)
    app._last_auto_report_date = None
    app._run_auto_report('Indian Only')
    yield wait(lambda: not app._auto_report_running, 400)
    trading, why = scheduled_report.is_trading_day()
    if trading:
        check('auto report sends', len(sent) == n + 1, app.status_lbl.cget('text'))
        ok2, msg2 = scheduled_report.run_scheduled_report()
        check('auto report not sent twice', not ok2 and 'already' in msg2, msg2)
    else:
        check('auto report skips non-trading day', len(sent) == n and why in app.status_lbl.cget('text'),
              app.status_lbl.cget('text'))
    json.dump({'enabled': True, 'hour': (now.tm_hour - 5) % 24, 'minute': 0, 'report_type': 'Indian Only'},
              open(m.SCHEDULE_FILE, 'w'))
    if os.path.exists(scheduled_report.STATE_FILE):
        os.remove(scheduled_report.STATE_FILE)
    ok3, msg3 = scheduled_report.run_scheduled_report(max_late_hours=3)
    check('late Windows-task run skipped', not ok3 and ('outside the window' in msg3 or 'Skipped' in msg3), msg3)


def s_misc():
    app.view_log()
    root.update()
    close_toplevels()
    root.event_generate('<F1>')
    app._on_escape()
    app._setup_market_status()
    app.update_dash()
    app.nb.select(app.help_tab)
    root.update()
    yield None


def s_fixes():
    """Bugs found by the Oct 2026 deep scan - each check fails on the old code."""
    import io, contextlib
    import numpy as np
    import pandas as pd
    import ta
    import market_data, scoring
    from corporate_actions_engine import CorporateActionsEngine, NSECorporateActions

    # 1. the daily report must give every stock the scan's own score and signal
    app.start_scan()                           # fresh scan: earlier steps changed the weights
    yield wait(lambda: not app.scanning, 400)
    scan = {r['symbol']: r for r in app.results if not r.get('hourly')}   # (1-hour candles can move between the two)
    with contextlib.redirect_stdout(io.StringIO()):
        rep = daily_report.StockAnalyzer().analyze_batch(list(scan), 'NSE', len(scan))
    differ = [f"{s['symbol']} scan {scan[s['symbol']]['score']} {scan[s['symbol']]['rec']} / report {s['score']} {s['recommendation']}"
              for s in rep if abs(s['score'] - scan[s['symbol']]['score']) > 0.05 or s['recommendation'] != scan[s['symbol']]['rec']
              or s['supertrend'] != scan[s['symbol']]['st_sig']]
    check('daily report scores match the scan', len(rep) >= len(scan) - 1 and not differ, f"{len(rep)} stocks; {differ[:3]}")

    # 2. report summary: each company once, real news only, the real Nifty 50
    with contextlib.redirect_stdout(io.StringIO()):
        report = daily_report.DailyReportGenerator().generate_report(watchlist=None, include_us=False, include_india=True)
    picks = [p['symbol'] for p in report['top_picks']]
    members = {s['symbol'] for k in ('nifty50', 'sensex30') for s in report['sections'][k]['stocks']}
    check('report: no stock twice in top picks, totals count each company once',
          len(picks) == len(set(picks)) and report['summary']['total_stocks'] == len(members),
          f"picks {picks}; total {report['summary']['total_stocks']} vs {len(members)} companies")
    check('report: no placeholder news', all(n.get('source') != 'Auto' for n in report['news']),
          str([(n.get('title', '')[:40], n.get('source')) for n in report['news'][:3]]))
    passed.append(f"INFO news items in the report: {len(report['news'])} "
                  f"({sorted({n.get('publisher') for n in report['news']})})")
    nifty = daily_report.nifty50_stocks()
    check('Nifty 50 list from NSE', 45 <= len(nifty) <= 55 and 'RELIANCE' in nifty and report['sections']['nifty50']['total'] >= 45,
          f"{len(nifty)} symbols, {report['sections']['nifty50']['total']} analysed")
    check('Sensex list has 30 current members', len(set(daily_report.SENSEX30_STOCKS)) == 30
          and report['sections']['sensex30']['total'] >= 28, f"{report['sections']['sensex30']['total']} analysed")

    # 3. 1-month chart in a month with few trading days (17 candles) used to say "No data"
    days = pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=300)
    days = days[:-22].append(days[-22:][::5]).append(days[-12:])       # thin out the last month
    px = 100 + np.cumsum(np.random.default_rng(3).normal(0, 1, len(days)))
    thin = pd.DataFrame({'Open': px, 'High': px + 1, 'Low': px - 1, 'Close': px, 'Volume': 1e5}, index=days)
    thin = thin[~thin.index.duplicated()].sort_index()
    n_month = len(market_data.slice_period(thin, '1mo'))
    real = market_data.load_scan_history
    market_data.load_scan_history = lambda symbols, **k: {'ZZTHIN': thin}
    try:
        got = m.Analyzer().fetch('ZZTHIN', '1mo')
    finally:
        market_data.load_scan_history = real
    check('1-month chart with under 20 candles', n_month < 20 and len(got) == n_month, f"{n_month} candles in the month, got {len(got)}")

    # 4. corporate actions: NSE + BSE announce the same event - list it once; amounts only for dividends
    same = CorporateActionsEngine._same_event
    nse = {'ex_date': '2026-09-15', 'category': 'dividend', 'amount': 7.0, 'source': 'NSE', 'purpose': 'Dividend - Rs 7 Per Share'}
    bse = {'ex_date': '2026-09-15', 'category': 'dividend', 'amount': 7.0, 'source': 'BSE', 'purpose': 'Final Dividend - Rs. - 7.0000'}
    special = dict(bse, amount=1.0, purpose='Special Dividend - Rs. - 1.0000')
    check('corporate: same event on NSE and BSE listed once', same(nse, bse) and not same(nse, special)
          and not same(nse, dict(bse, ex_date='2026-09-16')) and not same(nse, dict(bse, category='bonus')))
    parsed = NSECorporateActions()._parse_nse_response({'data': [
        {'symbol': 'A', 'subject': 'Face Value Split (Sub-Division) - From Rs 10/- Per Share To Re 1/- Per Share', 'exDate': '01-Oct-2026'},
        {'symbol': 'B', 'subject': 'Rights 3:19 @ Premium Rs 74/-', 'exDate': '01-Oct-2026'},
        {'symbol': 'C', 'subject': 'Interim Dividend - Rs 8.50 Per Share', 'exDate': '01-Oct-2026'}]})
    check('corporate: amount only for dividends', [p['amount'] for p in parsed] == [0.0, 0.0, 8.5], str([(p['category'], p['amount']) for p in parsed]))

    # 5. stop-loss / targets can never be zero or negative
    crash = {'price': 5.0, 'atr': 6.0}
    levels = [m.TargetCalc.calc(crash, rec) for rec in ('BUY', 'HOLD', 'SELL')]
    check('targets never below zero', all(min(t['sl'], t['t1'], t['t2'], t['t3']) > 0 for t in levels), str(levels[1]))
    normal = m.TargetCalc.calc({'price': 100.0, 'atr': 2.0}, 'BUY')
    check('targets from the ATR when a stock has no levels', (normal['sl'], normal['t1'], normal['t2'], normal['t3'], normal['rr']) == (97.0, 103.0, 105.0, 108.0, 1.67), str(normal))

    # 6. SuperTrend's ATR is the standard (Wilder) one, as on broker charts
    df = app.analyzer.fetch(next(iter(scan)), '2y')
    high, low, close = df['High'].values, df['Low'].values, df['Close'].values
    tr = np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
    tr[0] = high[0] - low[0]
    standard = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], 10).average_true_range().values
    check('SuperTrend uses the standard ATR', np.allclose(scoring._wilder(tr, 10)[9:], standard[9:]))

    # 7. import: a file saved by Excel starts with an invisible marker, and has a heading row
    orig = list(app.watchlist)
    paths['open'] = os.path.join(OUT, 'excel_saved.csv')
    with open(paths['open'], 'w', encoding='utf-8-sig', newline='') as f:
        f.write("Symbol,Qty\r\nTCS,10\r\nINFY,5\r\n")
    app.watchlist = []
    app.import_list()
    check('import: first symbol kept, heading not added', sorted(app.watchlist) == ['INFY', 'TCS'], str(app.watchlist))
    app.watchlist = orig
    app.refresh_watchlist()
    app.save_watchlist()

    # 8. an unreadable score history must not be overwritten by the next scan
    before = open(score_history.HISTORY_FILE, encoding='utf-8').read()
    real_reader = score_history.csv.DictReader
    def broken(*a, **k):
        raise PermissionError('locked')
    score_history.csv.DictReader = broken
    try:
        try:
            score_history.record(app.results[:1])
            raised = False
        except PermissionError:
            raised = True
    finally:
        score_history.csv.DictReader = real_reader
    check('score history is not wiped when it cannot be read', raised and open(score_history.HISTORY_FILE, encoding='utf-8').read() == before)

    # 9. PDFs no longer carry the full-size logo
    paths['save'] = os.path.join(OUT, 'small.pdf')
    app.export_pdf()
    size = os.path.getsize(paths['save']) // 1024
    check('pdf export is small', 2 < size < 400, f"{size} KB")
    yield None


def s_improvements():
    """Oct 2026 improvements: support/resistance targets, real sector rotation, holiday-aware market
    light, and the unused AI / live-trading modules removed."""
    import numpy as np
    import pandas as pd
    import requests
    import scoring

    # ---- 1. stop-loss and targets sit on support / resistance ----
    levels = {'support': [(99.5, 1), (96.0, 3), (90.0, 2)], 'resistance': [(100.6, 1), (104.0, 2), (109.0, 1), (115.0, 4)]}
    data = {'price': 100.0, 'atr': 2.0, 'levels': levels}
    buy, sell, hold = (m.TargetCalc.calc(data, rec) for rec in ('BUY', 'SELL', 'HOLD'))
    check('buy: stop under the support, targets at the resistances',
          (buy['sl'], buy['t1'], buy['t2'], buy['t3'], buy['rr']) == (95.5, 104.0, 109.0, 115.0, 2.0)
          and 'support at 96.00, tested 3 times' in buy['basis']['sl'] and 'resistance' in buy['basis']['t1'], str(buy))
    check('sell: stop over the resistance, targets at the supports',
          (sell['sl'], sell['t1'], sell['t2'], sell['t3'], sell['rr']) == (104.5, 96.0, 90.0, 88.0, 2.22)
          and 'resistance at 104.00' in sell['basis']['sl'] and 'ATR' in sell['basis']['t3'], str(sell))
    check('hold: reward is measured to target 1', (hold['sl'], hold['t1'], hold['rr']) == (95.5, 104.0, 0.89), str(hold))
    far = m.TargetCalc.calc({'price': 100.0, 'atr': 2.0, 'levels': {'support': [(80.0, 5)], 'resistance': []}}, 'BUY')
    check('a support too far away is not used for the stop', far['sl'] == 97.0 and 'ATR' in far['basis']['sl'], str(far))

    days = pd.bdate_range('2025-01-01', periods=220)
    zig = np.interp(np.arange(220), [0, 20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 219],
                    [100, 110, 90, 110, 90, 110, 90, 110, 90, 110, 90, 100])
    frame = pd.DataFrame({'Open': zig, 'High': zig + 0.5, 'Low': zig - 0.5, 'Close': zig, 'Volume': 1e5}, index=days)
    found = scoring.support_resistance(frame, atr=1.5)
    check('levels are found where the price turned',
          any(abs(p - 110.5) < 0.6 and n >= 4 for p, n in found['resistance'])
          and any(abs(p - 89.5) < 0.6 and n >= 4 for p, n in found['support']), str(found))

    bad, ratios, on_level = [], set(), 0
    for r in app.results:
        t = r['targets']
        ordered = (t['t3'] <= t['t2'] <= t['t1'] < t['price'] < t['sl']) if t['pos'] == 'SHORT' else (t['sl'] < t['price'] < t['t1'] <= t['t2'] <= t['t3'])
        if not ordered or min(t['sl'], t['t1'], t['t2'], t['t3']) <= 0:
            bad.append((r['symbol'], t))
        ratios.add(t['rr'])
        on_level += 'ATR' not in t['basis']['sl']
    check('scan: every stock has ordered, positive levels', not bad, str(bad[:2]))
    check('scan: risk:reward differs from stock to stock', len(ratios) >= min(5, len(app.results) // 2)
          and on_level >= len(app.results) // 2, f"{len(ratios)} different ratios; {on_level}/{len(app.results)} stops on a support/resistance")
    app.update_targets(app.results[0])
    root.update()
    shown = [str(w.cget('text')) for w in descendants(app.tg_frame) if w.winfo_class() == 'Label']
    check('targets tab says where each level comes from', sum(('support' in s.lower() or 'resistance' in s.lower() or 'ATR' in s) for s in shown) >= 4,
          str([s for s in shown if '|' in s][:2]))

    # ---- 2. sector rotation: strength AND direction ----
    rot = m.sector_rotation
    check('sector rotation rules', [rot(60, 3, 50), rot(60, -3, 50), rot(40, 3, 50), rot(40, -3, 50), rot(60, -0.5, 50), rot(40, 0.5, 50),
                                    rot(60, None, 50), rot(40, None, 50)]
          == ['LEADING', 'WEAKENING', 'IMPROVING', 'LAGGING', 'LEADING', 'LAGGING', 'LEADING', 'LAGGING'])
    app.analyze_sectors()
    yield wait(lambda: not getattr(app, '_sector_busy', False), 120)
    cols = list(app.sector_tree['columns'])
    rows = [dict(zip(cols, app.sector_tree.item(i)['values'])) for i in app.sector_tree.get_children()]
    with_change = [r for r in rows if is_number(r['Chg'])]
    check('sector tab shows each sector\'s change', 'Chg' in cols and len(with_change) >= len(rows) - 1
          and all(r['Rotation'] in ('LEADING', 'WEAKENING', 'IMPROVING', 'LAGGING') for r in rows)
          and 'since the scan of' in app.sector_status.cget('text'), f"{[(r['Sector'], r['Chg'], r['Rotation']) for r in rows[:4]]}")
    falling = [r for r in rows if is_number(r['Chg']) and float(str(r['Chg'])) < -m.ROTATION_FLAT]
    rising = [r for r in rows if is_number(r['Chg']) and float(str(r['Chg'])) > m.ROTATION_FLAT]
    check('falling sectors are never LEADING/IMPROVING, rising ones never WEAKENING',
          all(r['Rotation'] in ('WEAKENING', 'LAGGING') for r in falling) and all(r['Rotation'] in ('LEADING', 'IMPROVING') for r in rising),
          f"{len(falling)} falling, {len(rising)} rising")

    # ---- 3. market light knows NSE holidays; the holiday list is refreshed weekly ----
    monday = datetime(2026, 10, 5)
    st = m.market_status
    check('market hours', [st(monday.replace(hour=h, minute=mi))[0] for h, mi in ((9, 14), (9, 15), (12, 0), (15, 30), (15, 31))]
          == [False, True, True, True, False] and not st(datetime(2026, 10, 10, 11, 0))[0])
    check('market closed on an NSE holiday', st(monday.replace(hour=11), {'2026-10-05'}) == (False, 'Market closed: NSE holiday')
          and st(monday.replace(hour=11), {'2026-10-06'})[0])
    today, year = datetime.now().strftime('%Y-%m-%d'), datetime.now().year
    real_cached = scheduled_report.cached_holidays
    scheduled_report.cached_holidays = lambda y: {today}
    try:
        app._update_market_light()
    finally:
        scheduled_report.cached_holidays = real_cached
    expect = 'Market closed: NSE holiday' if datetime.now().weekday() < 5 else 'Market closed'
    check('the light shows the holiday', app.market_status_lbl.cget('text') == expect, app.market_status_lbl.cget('text'))
    app._update_market_light()

    hfile = scheduled_report.HOLIDAY_FILE
    saved_text = hfile.read_text() if hfile.exists() else None
    real_get, calls = requests.get, []

    class FakeResponse:
        def json(self):
            return {'CM': [{'tradingDate': f'26-Jan-{year}'}, {'tradingDate': f'15-Aug-{year}'}]}

    def fake_get(*a, **k):
        calls.append(a)
        if calls[0] == 'fail':
            raise ConnectionError('offline')
        return FakeResponse()

    requests.get = fake_get
    try:
        hfile.write_text(json.dumps({str(year): [f'{year}-01-26']}))                 # list saved by the old version: no date
        got_old = scheduled_report._nse_holidays(year)
        n_after_old = len(calls)
        got_fresh = scheduled_report._nse_holidays(year)                             # downloaded just now: must not ask again
        stale = json.loads(hfile.read_text())
        stale['fetched'][str(year)] = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        hfile.write_text(json.dumps(stale))
        calls[:] = ['fail']
        got_offline = scheduled_report._nse_holidays(year)                           # a month old and NSE unreachable
    finally:
        requests.get = real_get
        if saved_text is None:
            hfile.unlink()
        else:
            hfile.write_text(saved_text)
    both = {f'{year}-01-26', f'{year}-08-15'}
    check('holiday list: old file refreshed, fresh one reused, saved one used offline',
          got_old == both and n_after_old == 1 and got_fresh == both and got_offline == both and len(calls) == 2,
          f"{got_old} / calls {n_after_old} / {got_offline}")

    # ---- 4. unused modules are gone ----
    check('AI and live-trading modules removed', not os.path.exists('ai_engine.py') and not os.path.exists('live_trading.py')
          and not hasattr(m, 'AI_OK') and 'ai' not in app.results[0] and 'ai' not in app.results[0]['data'])


def _fake_listing(n_days, seed):
    """Yahoo's data for a stock listed n_days trading days ago: (15-minute candles, daily candles).
    The daily candles carry the 'official' close and volume, which differ from the last trade."""
    import numpy as np
    import pandas as pd
    import market_data
    days = pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=n_days)
    stamps = [d + pd.Timedelta(hours=9, minutes=15 + 15 * i) for d in days for i in range(25)]   # 09:15 .. 15:15
    close = 200 + np.cumsum(np.random.default_rng(seed).normal(0, 0.6, len(stamps)))
    q15 = pd.DataFrame({'Open': close - 0.2, 'High': close + 0.5, 'Low': close - 0.5, 'Close': close,
                        'Volume': 50000.0}, index=pd.DatetimeIndex(stamps))
    daily = q15.groupby(q15.index.normalize()).agg(market_data._CANDLE)
    daily['Close'] += 1.0
    daily['Volume'] *= 1.1
    return q15, daily


def s_new_listing():
    """Stocks listed days ago must be scanned on 1-hour candles and get every figure the others get.
    Simulated (Yahoo is faked for three made-up symbols), so it doesn't need a real new listing."""
    import pandas as pd
    import market_data
    new, two_days, old = 'ZZNEWIPO', 'ZZDAYTWO', 'ZZOLDCO'
    q15, daily = _fake_listing(6, 7)
    fakes = {new + '.NS': (q15, daily),
             two_days + '.NS': _fake_listing(2, 8),
             # an old stock whose daily download came back nearly empty: Yahoo still has 40 days of candles
             old + '.NS': (_fake_listing(40, 9)[0], _fake_listing(3, 9)[1])}
    real = market_data._download

    def fake(tickers, tz=None, **kw):
        out = real([t for t in tickers if not t.startswith('ZZ')], tz=tz, **kw)
        for t in tickers:
            if t.startswith('ZZ'):
                out[t] = fakes[t][0 if kw.get('interval') == '15m' else 1] if t in fakes else pd.DataFrame(columns=market_data.COLUMNS)
        return out

    orig = list(app.watchlist)
    normal = app.results[0]['symbol'] if app.results else orig[0]
    market_data._download = fake
    try:
        df = market_data.load_scan_history([new])[new]
        hours = sorted(set(df.index.strftime('%H:%M')))
        check('new listing: 1-hour candles built from 15-minute ones', market_data.is_hourly(df) and len(df) == 42
              and hours == ['09:15', '10:15', '11:15', '12:15', '13:15', '14:15', '15:15']
              and df['Volume'].iloc[0] == 200000 and df['Volume'].iloc[6] == 50000
              and df['High'].iloc[0] == q15['High'].iloc[:4].max() and df['Close'].iloc[0] == q15['Close'].iloc[3],
              f"{len(df)} candles at {hours}")
        check('old stock with a failed daily download is not treated as a new listing',
              old not in market_data.load_scan_history([old]))

        app.watchlist = [new, two_days, old, normal]
        app.last_toast = None
        app.start_scan()
        yield wait(lambda: not app.scanning, 200)
        done = (app.last_toast[1] if app.last_toast else '').split('\n')
        rows = {cell(i, 'Symbol'): i for i in app.tree.get_children()}
        r = next((x for x in app.results if x['symbol'] == new), None)
        check('new listing scanned', r is not None and r['hourly'] and r['data']['days'] == 6,
              f"results: {[x['symbol'] for x in app.results]}")
        if r:
            filled = ['Price', 'Change%', 'RSI', 'Score', '52W High', '52W Low', 'ATR', 'Traded/day (Cr)']
            check('new listing has every figure', all(is_number(cell(rows[new], c)) for c in filled)
                  and cell(rows[new], 'SuperTrend') in ('BUY', 'SELL') and cell(rows[new], 'Candle') == '1 Hour'
                  and cell(rows[new], 'vs Nifty 3M') == 'N/A' and cell(rows[normal], 'Candle') == 'Daily',
                  str(app.tree.item(rows[new])['values']))
            expect = (q15['Close'].iloc[-1] / daily['Close'].iloc[-2] - 1) * 100
            check("new listing: day's change from the official previous close", abs(r['change'] - expect) < 1e-6,
                  f"{r['change']:.4f} vs {expect:.4f}")
            expect = (daily['Close'] * daily['Volume']).mean() / 1e7
            check('new listing: traded value per day (not per hour)', abs(r['data']['liquidity_cr'] - expect) < 1e-6,
                  f"{r['data']['liquidity_cr']:.4f} vs {expect:.4f}")
            check('new listing: 52-week range covers its whole history', abs(r['high52'] - q15['High'].max()) < 1e-6
                  and abs(r['low52'] - q15['Low'].min()) < 1e-6)
            app.update_breakdown(r)
            app.update_targets(r)
            app.update_patterns(r)
            root.update()
            notes = [str(w.cget('text')) for f in (app.bd_frame, app.tg_frame) for w in f.winfo_children()
                     if w.winfo_class() == 'Label']
            check('new listing: details tabs say 1-hour candles', sum('1-hour' in n.lower() for n in notes) == 2)
            paths['save'] = os.path.join(OUT, 'new_listing.xlsx')
            app.export_results()
            from openpyxl import load_workbook
            ws = load_workbook(paths['save']).active
            candle = {ws.cell(i, 1).value: ws.cell(i, 18).value for i in range(2, ws.max_row + 1)}
            check('new listing: excel Candle column', ws.cell(1, 18).value == 'Candle' and candle.get(new) == '1 Hour'
                  and candle.get(normal) == 'Daily', str(candle))
            paths['save'] = os.path.join(OUT, 'new_listing.pdf')
            app.export_pdf()
            html = app._build_watchlist_email_html()
            check('new listing: marked in the pdf and email', os.path.getsize(paths['save']) > 500
                  and f'{new}*' in html and f'{normal}*' not in html and 'New listing' in html)
            for w in app.chart_frame.winfo_children():
                w.destroy()
            app.tree.selection_set(rows[new])
            app.chart_period_var.set('1mo')
            app.show_stock_chart()
            yield wait(lambda: any(w.winfo_class() == 'Canvas' for w in app.chart_frame.winfo_children()), 60)
            check('new listing: chart', any(w.winfo_class() == 'Canvas' for w in app.chart_frame.winfo_children()))
        check('listed 2 days ago: the scan says so', any('under 3 trading days' in l and two_days in l for l in done)
              and two_days not in rows, ' | '.join(done))
        check('old stock without daily data: still reported as failed', any('failed' in l and old in l and two_days not in l for l in done)
              and old not in rows, ' | '.join(done))
        rep = daily_report.StockAnalyzer().analyze_batch([new, two_days, old, normal], 'NSE', 4)
        by = {x['symbol']: x for x in rep}
        check('new listing in the daily report', set(by) == {new, normal} and by[new]['hourly'] and not by[normal]['hourly']
              and r is not None and abs(by[new]['change_pct'] - r['change']) < 0.01, str(sorted(by)))
    finally:
        market_data._download = real
        app.watchlist = orig


def s_company_search():
    """Add a stock by typing the first letters of the company's name."""
    import symbols
    S = symbols
    check('company list loaded', len(S.load()) > 5000, f"{len(S.load())} companies")
    top = S.search('relia', 5)
    check('search by the first letters of the name', bool(top) and top[0][:4] == ['Reliance Industries Limited', 'RELIANCE', 'RELIANCE', '500325'],
          str(top[:1]))
    check('search by several words, a symbol or a BSE code', S.search('tata consult')[0][S.ADD] == 'TCS'
          and S.search('infy')[0][S.NAME].startswith('Infosys') and S.search('500325')[0][S.ADD] == 'RELIANCE'
          and S.search('state bank')[0][S.ADD] == 'SBIN')
    bse_only = S.search('creative castings')
    check('a BSE-only company is found too', bool(bse_only) and bse_only[0][S.NSE] == '' and bse_only[0][S.BSE] == 'CREATIVE', str(bse_only[:1]))
    check('NSE SME stocks are added the way their prices are listed', any(e[S.ADD] == e[S.NSE] + '-SM' for e in S.load())
          and all(m.re.match(r'^[A-Z0-9][A-Z0-9&_.-]{0,19}$', e[S.ADD]) for e in S.load()))
    check('nothing matches nonsense', S.search('zzqqxx') == [])

    orig = list(app.watchlist)
    query, target = next((q, S.search(q)[0]) for q in ('nestle', 'asian paints', 'titan comp', 'wipro', 'maruti suz')
                         if S.search(q)[0][S.ADD] not in app.watchlist)
    app.entry.delete(0, tk.END)
    app.entry.insert(0, query)
    app.suggest.update()
    root.update()
    rows = [app.suggest.tree.item(i)['values'] for i in app.suggest.tree.get_children()]
    check('suggestions drop down with the full name and both symbols', app.suggest.visible() and bool(rows)
          and rows[0][0] == target[S.NAME] and target[S.NSE] in str(rows[0][1]) and target[S.CODE] in str(rows[0][2]), str(rows[:1]))
    app.add_stock()                                   # Enter
    root.update()
    check('Enter adds the highlighted company', target[S.ADD] in app.watchlist and not app.suggest.visible() and app.entry.get() == '',
          f"{target[S.ADD]} in watchlist: {target[S.ADD] in app.watchlist}")
    check('the watchlist shows the company name', any(r.startswith(target[S.ADD] + '  ' + target[S.NAME]) for r in app.wl_list.get(0, tk.END))
          and app._wl_symbol(next(r for r in app.wl_list.get(0, tk.END) if r.startswith(target[S.ADD] + '  '))) == target[S.ADD])
    check('the toast names the company', app.last_toast == (f"Added {target[S.ADD]}", target[S.NAME]), str(app.last_toast))

    # part of a name + Enter before the list was looked at: the list opens, nothing is added yet
    n = len(app.watchlist)
    app.entry.insert(0, 'hdfc l')
    app.add_stock()
    root.update()
    check('part of a name + Enter opens the list first', len(app.watchlist) == n and app.suggest.visible() and len(app.suggest.items) >= 1)
    app.suggest._move(1)
    app.suggest._move(-1)
    picked = app.suggest.selected()
    app.suggest._on_escape(None)
    check('Esc closes the list', not app.suggest.visible())
    app.suggest.update()
    app.suggest.on_pick(app.suggest.items[0])         # a click
    check('a click adds the company', picked is not None and picked[S.ADD] in app.watchlist, str(picked))

    # a symbol the list doesn't know (listed in the last few days) is still added as typed
    app.entry.delete(0, tk.END)
    app.entry.insert(0, 'zznewipo')
    app.add_stock()
    check('an unknown symbol is added as typed', 'ZZNEWIPO' in app.watchlist)
    app.entry.insert(0, 'no such company name')
    n = len(app.watchlist)
    app.add_stock()
    check('a name that matches nothing adds nothing', len(app.watchlist) == n and app.last_toast[0] == 'No company found')
    app.entry.delete(0, tk.END)
    app.suggest.hide()
    app.watchlist[:] = orig
    app.save_watchlist()
    app.refresh_watchlist()
    yield None


def s_appearance():
    import ui_theme as ui
    from tkinter import ttk
    settings = lambda: json.load(open(m.APP_SETTINGS_FILE))
    check('starts in the saved look (light by default)', m.THEME['mode'] == settings().get('appearance', 'light'))
    if m.THEME['mode'] == 'dark':        # the copied settings may say dark: start the checks from light
        app.apply_appearance('light')
        yield wait(lambda: m.THEME['mode'] == 'light' and str(app.root.cget('bg')).lower() == ui.LIGHT['bg'].lower(), 10)
        root.update()
    check('3D buttons behave like buttons', isinstance(app.scan_btn, ui.RoundButton) and app.scan_btn.cget('state') == 'normal'
          and app.scan_btn['text'] == 'Scan all stocks' and app.bt_run_btn.cget('text') == 'Run Backtest')
    app.bt_apply_btn.configure(state=tk.DISABLED)
    check('disabled 3D button ignores clicks', app.bt_apply_btn.cget('state') == 'disabled')
    calls = []
    btn = ui.RoundButton(root, "Test", command=lambda: calls.append(1), theme=m.THEME)
    btn.invoke()
    btn.configure(state=tk.DISABLED)
    btn.invoke()
    btn.destroy()
    check('3D button runs its command once (not when disabled)', calls == [1])

    # the market map and the sector chart in 3D
    app.show_market_map()
    root.update()
    check('3D market map drawn', app._chart_state == ('map',)
          and any(w.winfo_class() == 'Canvas' for w in app.chart_frame.winfo_children()))
    app.analyze_sectors()
    yield wait(lambda: not getattr(app, '_sector_busy', False), 120)
    yield wait(lambda: any(w.winfo_class() == 'Canvas' for w in app.sector_3d_frame.winfo_children()), 10)
    check('3D sector chart drawn', any(w.winfo_class() == 'Canvas' for w in app.sector_3d_frame.winfo_children()))

    # a scan in progress blocks the switch
    app.scanning = True
    app.apply_appearance('dark')
    app.scanning = False
    check('switch waits for a running scan', m.THEME['mode'] == 'light' and 'scan' in (app.last_toast or ('', ''))[0].lower())

    # switch to dark: everything is still there afterwards
    app.tree.selection_set(app.tree.get_children()[0])
    app.show_details(None)
    app.nb.select(1)
    before = (len(app.tree.get_children()), app.wl_list.size(), app.corp_tree.get_children().__len__(),
              len(app.sector_tree.get_children()), app._detail_symbol)
    app.apply_appearance('dark')
    yield wait(lambda: m.THEME['mode'] == 'dark' and str(app.root.cget('bg')).lower() == ui.DARK['bg'].lower(), 10)
    root.update()
    after = (len(app.tree.get_children()), app.wl_list.size(), app.corp_tree.get_children().__len__(),
             len(app.sector_tree.get_children()), app._detail_symbol)
    check('dark mode on', m.THEME['mode'] == 'dark' and settings().get('appearance') == 'dark'
          and ttk.Style().lookup('Treeview', 'background').lower() == ui.DARK['card'].lower())
    check('everything still shown after the switch', before == after and app.nb.index('current') == 1, f"{before} -> {after}")
    check('details redrawn in dark', len(app.bd_frame.winfo_children()) > 2 and len(app.tg_frame.winfo_children()) > 2)
    check('all tabs rebuilt', len(app.nb.tabs()) == 11 and len(app.tabbar.labels) == 11)
    check('sector 3D chart redrawn', any(w.winfo_class() == 'Canvas' for w in app.sector_3d_frame.winfo_children()))
    check('dark section boxes', all(str(w.cget('bg')).lower() == ui.DARK['card'].lower()
                                    for w in descendants(root) if w.winfo_class() == 'Labelframe'))
    app.show_market_map()
    root.update()
    check('3D market map in dark', any(w.winfo_class() == 'Canvas' for w in app.chart_frame.winfo_children()))

    # animations off and on (saved)
    app.animations_var.set(False)
    app.toggle_animations()
    check('animations off', not ui.Motion.enabled and settings().get('animations') is False)
    app.update_dash()
    check('counters jump straight to the end with animations off', app.summary.v == 1.0)
    app.animations_var.set(True)
    app.toggle_animations()
    check('animations on', settings().get('animations') is True and ui.Motion.enabled == ui.windows_allows_animation())

    # and back to light
    app.apply_appearance('light')
    yield wait(lambda: m.THEME['mode'] == 'light' and str(app.root.cget('bg')).lower() == ui.LIGHT['bg'].lower(), 10)
    root.update()
    check('back to light', m.THEME['mode'] == 'light' and settings().get('appearance') == 'light'
          and len(app.tree.get_children()) == before[0])


STEPS = [('startup', s_startup), ('one copy at a time', s_single_instance), ('watchlist', s_watchlist),
         ('company search', s_company_search),
         ('import/save lists', s_import_save_lists), ('scan', s_scan), ('score history', s_history_compare),
         ('results table', s_results_table), ('details', s_details_every_stock), ('exports', s_exports),
         ('sector', s_sector), ('charts', s_charts), ('corporate', s_corporate), ('backtest', s_backtest),
         ('settings', s_settings), ('reports + email', s_reports), ('auto report', s_auto_report), ('misc', s_misc),
         ('deep-scan fixes', s_fixes), ('improvements', s_improvements), ('new listings (1-hour candles)', s_new_listing),
         ('appearance: light/dark, animations, 3D', s_appearance)]


class Driver:
    """Runs the steps inside Tk's main loop (background threads post results via root.after)."""
    def __init__(self):
        self.steps = iter(STEPS)
        self.gen = None
        self.waiting = None

    def tick(self):
        try:
            if self.gen is None:
                self.name, fn = next(self.steps)
                self.gen = fn()
                self.waiting = None
                print(f"... {self.name}", flush=True)
            if self.waiting:
                cond, timeout = self.waiting
                if not cond() and time.time() - self.wstart < timeout:
                    root.after(250, self.tick)
                    return
                if not cond():
                    problems.append(f"TIMEOUT in step '{self.name}' after {timeout}s")
            self.waiting = next(self.gen)
            self.wstart = time.time()
        except StopIteration:
            if self.gen is None:          # no more steps
                return finish()
            self.gen = None
        except Exception:
            problems.append(f"STEP CRASHED '{getattr(self, 'name', '?')}': {traceback.format_exc()[-900:]}")
            self.gen = None
        root.after(50, self.tick)


def finish():
    try:
        keyring.delete_password(TEST_SERVICE, SENDER)
    except Exception:
        pass
    print("\n".join(passed))
    print(f"\nemails captured by the fake mail server: {len(sent)} | dialogs: "
          f"{sum(1 for d in dialog_log if d[0] == 'info')} info, {sum(1 for d in dialog_log if d[0] == 'warn')} warning, "
          f"{sum(1 for d in dialog_log if d[0] == 'error')} error")
    print(f"\n==== PROBLEMS: {len(problems)} ====")
    print("\n".join(problems) if problems else "none")
    root.quit()


root.after(1500, Driver().tick)
root.mainloop()
try:
    root.destroy()
except Exception:
    pass
sys.exit(1 if problems else 0)
