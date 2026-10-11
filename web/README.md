# Web version (Vercel, free)

The scanner as a website for you and your friends: sign in from any phone or PC, keep your own
watchlist, scan, and see each stock's score, stop-loss, targets and patterns, price charts and
the 3D market map, in light or dark mode.

It scores stocks with **the desktop app's own code** (`scoring.py`, `market_data.py`,
`pattern_recognition.py`, copied into `api/_core` by `sync_core.py`), so a stock gets the same
score on the website as in the desktop app.

## How it gets online

The code lives in a private GitHub repository (`nileshshah1807-sys/drs-market-analysis`) that is
connected to the Vercel project **drs-market-analysis**. Every push to `main` is put online by
Vercel in about a minute.

- **To publish a change:** double-click **`deploy_web.bat`** in the main folder. It copies the
  latest scoring code, runs the checks (nothing is published if one fails), then commits and
  pushes to GitHub.
- **Settings kept in Vercel** (project > Settings > Environment Variables): `SECRET_KEY` (signs
  the sign-in cookies), `INVITE_CODE` (what friends type to create an account) and the database's
  `KV_REST_API_URL` / `KV_REST_API_TOKEN` (added by Storage > Upstash for Redis, free plan,
  auto-upgrade off). The invite code is also noted on this PC in `.vercel/drs_setup.json`.
- The Vercel project's Root Directory is `web`.

## Friends

Send them the address and the invite code. Each person creates their own user name and password
and has their own watchlist and scan history. To change the code, edit `INVITE_CODE` in the Vercel
project (Settings > Environment Variables) and redeploy; delete it to stop new sign-ups.

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
| `deploy.py` | What `deploy_web.bat` runs: sync, checks, commit, push |
| `dev_server.py` | Runs the site on this PC |
| `tests/test_web.py`, `tests/test_ui.py` | Server checks; page checks in Microsoft Edge |
