# Web version (Vercel, free)

The scanner as a website for you and your friends: sign in from any phone or PC, keep your own
watchlist, scan, and see each stock's score, stop-loss, targets and patterns, price charts and
the 3D market map, in light or dark mode.

It scores stocks with **the desktop app's own code** (`scoring.py`, `market_data.py`,
`pattern_recognition.py`, copied into `api/_core` by `sync_core.py`), so a stock gets the same
score on the website as in the desktop app.

## Put it online (first time, about 10 minutes)

1. Create a free account at <https://vercel.com/signup>.
2. Double-click **`deploy_web.bat`** in the main folder.
   - A browser window opens to sign in to Vercel; answer the questions as the window says.
   - Choose an **invite code**: friends type it once, when they create their account.
3. Connect the free database (once): <https://vercel.com/dashboard> > project
   **drs-market-analysis** > **Storage** > **Create Database** > **Upstash for Redis** > Free >
   connect it to the project.
4. Double-click **`deploy_web.bat`** again. Your site's address ends in `.vercel.app`
   (see the project in the Vercel dashboard).

After a change to the app, run `deploy_web.bat` again: it copies the latest scoring code, runs the
checks (nothing is uploaded if one fails) and uploads.

## Friends

Send them the address and the invite code. Each person creates their own user name and password
and has their own watchlist and scan history. To stop new sign-ups, delete `INVITE_CODE` in the
Vercel project (Settings > Environment Variables) and redeploy.

## Try it on this PC first

Double-click **`run_web_locally.bat`** (opens <http://localhost:8000>; invite code on this PC: `dev`).

## Good to know

- **Free plan = personal, non-commercial use.** Fine for you and friends; charging people needs
  Vercel Pro.
- **Prices come from Yahoo Finance**, like the desktop app. If Yahoo ever refuses Vercel's
  servers, scans come back as "No data"; trying again later usually works.
- A scan runs in batches of 8 stocks (a free Vercel request may run 60 seconds at most).
- Market open/closed is worked out from Indian time (weekdays 09:15-15:30); NSE holidays aren't
  known to the website.
- Not in the web version: corporate actions, backtest, sector tab, PDF/Excel export, email
  reports. Use the desktop app for those.

## Files

| File | Purpose |
|------|---------|
| `api/index.py` | The server: sign-in, watchlists, scan, charts (Flask) |
| `api/_core/` | Copies of the desktop app's scoring code - edit the originals, not these |
| `public/` | The page: `index.html`, `app.css`, `app.js` |
| `vercel.json`, `requirements.txt`, `.python-version` | Vercel settings |
| `deploy.py` | What `deploy_web.bat` runs |
| `dev_server.py` | Runs the site on this PC |
| `tests/test_web.py`, `tests/test_ui.py` | Server checks; page checks in Microsoft Edge |
