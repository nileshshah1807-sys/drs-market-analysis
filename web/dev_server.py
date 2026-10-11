"""Run the web version on this PC (before or instead of deploying to Vercel).

    python web/dev_server.py            then open http://localhost:8000
                                        (invite code for new accounts on this PC: dev)

Accounts and watchlists are kept in web/.dev_store.json. Nothing here goes to the internet
except the price downloads from Yahoo Finance.
"""
import os
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent
os.environ.setdefault('DRS_DEV', '1')
os.environ.setdefault('DRS_STORE_FILE', str(WEB / '.dev_store.json'))
sys.path.insert(0, str(WEB / 'api'))

import index  # noqa: E402

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    if os.environ.get('DRS_DEV_USER'):          # screenshots: everyone is signed in as this user
        index.DEV_USER = os.environ['DRS_DEV_USER']
    print(f"Open http://localhost:{port}   (stop with Ctrl+C)")
    index.app.run(host='127.0.0.1', port=port, debug=False, threaded=True)
