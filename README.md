# DR. NILESH SHAH'S MARKET ANALYSIS

Desktop app for technical analysis of Indian stocks (NSE/BSE). It scans your watchlist, scores each stock 0-100 from ten indicators, gives Buy/Hold/Sell signals with stop-loss and targets, tracks corporate actions, and emails a daily report.

The app is **`dr_shah_analysis.py`**. Older versions are in `old_versions/` and aren't needed.

## Quick Start (Windows)

1. Double-click **`DR Nilesh Shah Market Analysis.exe`**. No Python needed.
   Keep it in this folder, next to the `_internal` folder and your data files.
2. Or run from source: double-click **`run_app.bat`** (installs any missing packages, then starts the app).
3. Or from Command Prompt in this folder:
   ```
   python -m pip install -r requirements.txt
   python dr_shah_analysis.py
   ```

Mac/Linux: `./run_app.sh`

Use `python -m pip`, not plain `pip`: if you have more than one Python installed, plain `pip` can install packages into a different Python than the one that runs the app.

## Features

| Tab | What it does |
|-----|--------------|
| Watchlist | Add stocks by typing the first letters of the **company's name** (a list drops down with each company's NSE and BSE symbols) or its symbol; remove stocks, groups, sector filter, import (Excel, CSV, TXT, JSON, PDF) |
| Scan Results | Score, signal (shown as a marker: double up = strong buy, up = buy, bar = hold, down = sell, double down = strong sell), **change since the last scan**, **performance vs the Nifty 50**, 52-week range, ATR and daily traded value (F5 to scan). Signal changes slide in at the bottom right after each scan, and the rows that changed glow briefly |
| Score Breakdown / Stop-Loss & Targets / Pattern Analysis | Double-click a stock for details |
| Corporate Actions | Live dividends, splits, bonus, buybacks from NSE and BSE |
| Charts | Price with 20/50-day averages and volume (the lines draw themselves in), and the **3D market map**: every scanned stock by score, RS rating and strength against the Nifty, turning slowly - click to stop, drag to turn |
| Sector | Sector averages and rotation, with a **3D chart** of buy, hold and sell stocks per sector |
| Backtest | Checks whether the score predicted returns on your stocks' history; suggests weights and re-checks applied weights every 30 days |
| Settings | **Appearance (Light or Dark, animations on or off)**, email, scheduled report, liquidity threshold, scoring weights |

Exports: Excel, CSV, PDF, and email (watchlist or full market report).

### Look and feel

The app uses the light **Daylight** design; **Settings > Appearance** switches to **dark mode** (the window fades
and comes back in the new colours, with your scan results still there). Buttons are raised and press down when
clicked, the tab underline slides, the scan summary counts up, the score ring sweeps round, and the market light
pulses while the market is open. Turn the motion off in Settings > Appearance; if Windows' own
"Animation effects" setting is off, the app stays still too. The look lives in `ui_theme.py`.

## Scoring

Default indicator weights (change them in Settings, or apply the Backtest tab's suggestions -
the Backtest tab shows which weights are in use; Settings > Reset Defaults restores these):

| Indicator | Weight |
|-----------|--------|
| RS rating (vs the Nifty 50) | 12% |
| MACD | 12% |
| Moving averages (SMA 20/50/200, EMA 12/26) | 15% |
| SuperTrend | 11% |
| VWAP | 10% |
| Bollinger Bands | 8% |
| Stochastic | 8% |
| ADX | 8% |
| Volume (OBV) | 8% |
| Momentum (Williams %R, CCI) | 8% |

| Score | Signal |
|-------|--------|
| 75-100 | STRONG BUY |
| 60-74 | BUY |
| 45-59 | HOLD |
| 30-44 | SELL |
| 0-29 | STRONG SELL |

**RS rating** (1-99, replaces RSI in the score): the stock's price performance over the last 3, 6, 9 and
12 months - the last 3 months counting double - compared with the Nifty 50's, on a 1-99 scale in the style of
IBD's Relative Strength rating. **90 and above is the best** (scores 90 of 100); a stock that has done exactly
as well as the Nifty rates 50. The scale is set by `RS_RATING_TABLE` in `scoring.py` (performance vs the
Nifty -> rating): a scan can't rank a stock against every listed stock the way IBD does, so the table stands
in for that. A stock with under 3 months of history, or a scan without Nifty data, scores RS as neutral (50).
Weights saved before this change are kept: the old RSI weight becomes the RS weight.

Stocks trading less than Rs 1 crore a day (adjustable) are marked **LOW** liquidity: their stop-loss and targets are less reliable.

### Stop-loss and targets

The stop-loss sits just beyond the stock's nearest support (for a SELL, its nearest resistance) and the three
targets at its next resistance levels (for a SELL, supports). Levels are the swing highs and lows of the last 250
candles; turns within half an ATR of each other count as one level. A level closer than 0.75 ATR isn't used for
the stop and one further than 3 ATR is too far, and where a stock has no usable level a multiple of its ATR is
used instead - the Stop-Loss & Targets tab says which. Risk:Reward is the distance to Target 2 (Target 1 for a
HOLD) divided by the distance to the stop, so it differs from stock to stock. The rules are in `TargetCalc` in
`scoring.py`.

### Sector rotation

The Sector tab compares each sector's average score with your watchlist's average (strength) and with the same
stocks' scores about a week earlier, from the score history (direction): **LEADING** = stronger and not falling,
**WEAKENING** = stronger but falling, **IMPROVING** = weaker but rising, **LAGGING** = weaker and not rising.

### New listings

A stock listed less than a month ago has too few daily candles for the indicators, so it is scanned on
**1-hour candles** instead (the "Candle" column shows `1 Hour`; reports mark it with a `*`). Every indicator,
the patterns, and the ATR behind the stop-loss and targets then use hourly candles, so those levels sit closer
to the price. The day's change, 52-week range and traded value per day are still per day, and "vs Nifty" is N/A
until the stock has traded for the full period. A score needs 20 hourly candles - the 3rd trading day. After a
month the stock switches to daily candles like the rest.

The hourly candles are built from Yahoo's 15-minute candles: Yahoo's own 1-hour candles have the same prices
but no volume for the first hour of each NSE session.

## Web version

A website version for you and friends (free on Vercel): sign in from a phone or PC, own watchlist per
person, scan, stock details, price charts and the 3D market map, light/dark. It uses this app's own
scoring code. It is published by pushing to GitHub (Vercel deploys every push): double-click
**`deploy_web.bat`**. To try it on this PC, **`run_web_locally.bat`**. Details: [`web/README.md`](web/README.md).

## Daily email report

- The report scores every stock with the same code and weights as the scan (`scoring.py`), so a stock
  always has the same score and signal in both.
- "Nifty 50" is NSE's current list, downloaded weekly. "Sensex 30" is a list in `daily_report.py`
  (`SENSEX30_STOCKS`) kept by hand - BSE has no downloadable one - so update it when the Sensex changes
  (June and December).
- News headlines come from Yahoo Finance or, when it has none, the Economic Times and Mint market feeds.
- Settings > Email Report Configuration: enter a Gmail address and a Gmail **App Password** (https://myaccount.google.com/apppasswords), then Save and Test.
- The password is stored in **Windows Credential Manager**, not in `email_config.json`.
- Settings > Auto Report Scheduling > **Install Windows Task** emails the report on NSE trading days even when the app is closed (weekends and NSE holidays are skipped).

## Files

| File | Purpose |
|------|---------|
| `dr_shah_analysis.py` | Main app |
| `ui_theme.py` | Light (Daylight) and dark colours, fonts, 3D buttons, tab bar, slide-in messages, animations |
| `scoring.py` | Indicators, the 0-100 score and stop-loss/targets - one copy, used by the scan, the backtest and the daily report |
| `symbols.py`, `symbols_master.json` | Every NSE and BSE company (name, symbol on each exchange) for the "Add a stock" search. From the exchanges' own files; the app refreshes its copy weekly (`python symbols.py build` rebuilds the shipped list) |
| `market_data.py` | Batch price downloads with a disk cache (`data_cache/`) |
| `backtest.py` | Backtest engine |
| `score_history.py` | Score history (`score_history.csv`, one row per stock per day - opens in Excel) |
| `daily_report.py` | Daily report, PDF and email |
| `scheduled_report.py` | Scheduled email (Windows Task Scheduler) |
| `corporate_actions_engine.py`, `corporate_actions.py` | Corporate actions (live + fallback) |
| `pattern_recognition.py` | Chart and candlestick patterns |
| `run_app.bat`, `run.bat`, `install_dependencies.bat`, `setup.bat` | Launchers and installers |

Your own data (watchlist, settings, reports, cache, log) stays on your PC and is not tracked by git.

## Building the .exe

Double-click **`build_exe.bat`**. It builds the app with PyInstaller (about 2 minutes) and installs
`DR Nilesh Shah Market Analysis.exe` + `_internal\` into this folder. Close the app first.
The recipe is in `DR_Nilesh_Shah_Market_Analysis.spec`.

To check a build works: `"DR Nilesh Shah Market Analysis.exe" --self-test` writes `self_test_result.txt`.

To use the app on another PC, copy the `.exe` **and** the `_internal` folder together (e.g. in a zip).
There you'll need to enter the Gmail App Password again in Settings (it's stored in this PC's
Credential Manager). Windows may show a "Windows protected your PC" warning for a downloaded,
unsigned app: click "More info" > "Run anyway".

## Testing

Double-click **`run_tests.bat`** (about 5 minutes). It runs every feature of the app twice - as Python
and as the packaged .exe would - on a throwaway copy with a copy of your watchlist, so your data,
email and Windows task are never touched (emails go to a fake mail server). It ends with
"ALL PASSED" or a list of problems. The test is in `tests/`.

## Version control (git)

Every change is recorded, so any edit can be reviewed or undone:

```
git log --oneline          # list saved versions
git diff                   # see unsaved changes
git checkout -- <file>     # discard unsaved changes to a file
git revert <commit>        # undo a saved change
```

## Troubleshooting

- **"No module named ..."**: run `python -m pip install -r requirements.txt`
- **"tkinter not available"**: reinstall Python with the "tcl/tk and IDLE" option ticked
- **App doesn't start**: run `install_dependencies.bat`, then check `dr_shah_analysis.log`

## Disclaimer

For educational and informational purposes only. The signals come from technical analysis and are **not** financial advice. Do your own research and consult a financial advisor before investing.
