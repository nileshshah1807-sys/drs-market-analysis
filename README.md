# DR. NILESH SHAH'S MARKET ANALYSIS

Desktop app for technical analysis of Indian stocks (NSE/BSE). It scans your watchlist, scores each stock 0-100 from ten indicators, gives Buy/Hold/Sell signals with stop-loss and targets, tracks corporate actions, and emails a daily report.

The app is **`dr_shah_analysis.py`**. Older versions are in `old_versions/` and aren't needed.

## Quick Start (Windows)

1. Double-click **`run_app.bat`**. It installs any missing packages, then starts the app.
2. Or from Command Prompt in this folder:
   ```
   python -m pip install -r requirements.txt
   python dr_shah_analysis.py
   ```

Mac/Linux: `./run_app.sh`

Use `python -m pip`, not plain `pip`: if you have more than one Python installed, plain `pip` can install packages into a different Python than the one that runs the app.

## Features

| Tab | What it does |
|-----|--------------|
| Watchlist | Add/remove stocks, groups, sector filter, import (Excel, CSV, TXT, JSON, PDF) |
| Scan Results | Score, signal, 52-week range, ATR and daily traded value for every stock (F5 to scan) |
| Score Breakdown / Stop-Loss & Targets / Pattern Analysis | Double-click a stock for details |
| Corporate Actions | Live dividends, splits, bonus, buybacks from NSE and BSE |
| Charts | Price with 20/50-day averages and volume |
| Sector | Sector averages and rotation |
| Backtest | Checks whether the score predicted returns on your stocks' history; suggests weights |
| Settings | Email, scheduled report, liquidity threshold, scoring weights |

Exports: Excel, CSV, PDF, and email (watchlist or full market report).

## Scoring

Default indicator weights (change them in Settings, or apply the Backtest tab's suggestions):

| Indicator | Weight |
|-----------|--------|
| RSI (14) | 12% |
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

Stocks trading less than Rs 1 crore a day (adjustable) are marked **LOW** liquidity: their stop-loss and targets are less reliable.

## Daily email report

- Settings > Email Report Configuration: enter a Gmail address and a Gmail **App Password** (https://myaccount.google.com/apppasswords), then Save and Test.
- The password is stored in **Windows Credential Manager**, not in `email_config.json`.
- Settings > Auto Report Scheduling > **Install Windows Task** emails the report on NSE trading days even when the app is closed (weekends and NSE holidays are skipped).

## Files

| File | Purpose |
|------|---------|
| `dr_shah_analysis.py` | Main app |
| `market_data.py` | Batch price downloads with a disk cache (`data_cache/`) |
| `backtest.py` | Backtest engine |
| `daily_report.py` | Daily report, PDF and email |
| `scheduled_report.py` | Scheduled email (Windows Task Scheduler) |
| `corporate_actions_engine.py`, `corporate_actions.py` | Corporate actions (live + fallback) |
| `pattern_recognition.py`, `ai_engine.py` | Chart/candlestick patterns, ML engine |
| `run_app.bat`, `run.bat`, `install_dependencies.bat`, `setup.bat` | Launchers and installers |

Your own data (watchlist, settings, reports, cache, log) stays on your PC and is not tracked by git.

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
