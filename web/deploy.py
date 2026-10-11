"""Put the web version online on Vercel (free plan). deploy_web.bat in the main folder runs this.

Before the first time: create a free account at https://vercel.com/signup.
Each run: copies the scoring code from the desktop app, checks the web version on this PC
(nothing is uploaded if a check fails), uploads it, and the first time also sets the secret
key and the invite code your friends need to create an account.
"""
import json
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent
STATE = WEB / '.vercel' / 'drs_setup.json'
NPX = shutil.which('npx') or shutil.which('npx.cmd')


def say(text=''):
    print(text, flush=True)


def vercel(args, **kw):
    return subprocess.run([NPX, '--yes', 'vercel@latest', *args], cwd=WEB, **kw)


def env_names():
    r = vercel(['env', 'ls', 'production'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.stdout + r.stderr


def main():
    say("DR. NILESH SHAH'S MARKET ANALYSIS - put the web version online (Vercel, free)")
    say("=" * 78)
    if not NPX:
        say("Node.js is needed for Vercel's upload tool. Install the LTS version from https://nodejs.org, then run this again.")
        return 1

    say("\n[1/4] Copying the scoring code from the desktop app...")
    subprocess.run([sys.executable, str(WEB / 'sync_core.py')], check=True)

    say("\n[2/4] Checking the web version on this PC (about a minute)...")
    r = subprocess.run([sys.executable, str(WEB / 'tests' / 'test_web.py')], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    if r.returncode != 0:
        say(r.stdout[-3000:])
        say("The check found problems - nothing was uploaded.")
        return 1
    say("      all checks passed")

    if not (WEB / '.vercel' / 'project.json').exists():
        say("\nFirst time: connect this folder to your Vercel account.")
        say("  A browser window opens to sign in to Vercel. Then answer:")
        say("    Set up / link?                  Y (yes)")
        say("    Which scope?                    your account (press Enter)")
        say("    Link to an existing project?    N (no)")
        say("    Project name?                   type  drs-market-analysis  and press Enter")
        say("    Code directory?                 ./   (press Enter)")
        say("    Modify the settings?            N (no)\n")
        if vercel(['link']).returncode != 0:
            say("Linking failed - run this again.")
            return 1

    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if not state.get('secrets'):
        say("\n[one-time] Settings for logins")
        invite = ''
        while len(invite) < 4:
            invite = input("  Choose an invite code that friends type when they create an account (at least 4 characters): ").strip()
        for name, value in (('SECRET_KEY', secrets.token_hex(32)), ('INVITE_CODE', invite)):
            vercel(['env', 'rm', name, 'production', '--yes'], capture_output=True)
            if vercel(['env', 'add', name, 'production'], input=value, text=True).returncode != 0:
                say(f"Couldn't save {name} - run this again.")
                return 1
        state.update(secrets=True, invite=invite)
        STATE.write_text(json.dumps(state, indent=2))
        say(f"  Saved. Invite code: {invite}  (also noted in web\\.vercel\\drs_setup.json on this PC)")

    names = env_names()
    has_db = 'KV_REST_API_URL' in names or 'UPSTASH_REDIS_REST_URL' in names

    say("\n[3/4] Uploading to Vercel...")
    r = vercel(['deploy', '--prod'], stdout=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
    url = next((line.strip() for line in reversed((r.stdout or '').splitlines()) if line.strip().startswith('https://')), '')
    if r.returncode != 0:
        say(r.stdout or '')
        say("Upload failed (see above).")
        return 1

    say("\n[4/4] Done.")
    if not has_db:
        say("\nONE LAST STEP (only once) - connect the free database that keeps everyone's watchlist:")
        say("  1. Open https://vercel.com/dashboard and click the project  drs-market-analysis")
        say("  2. Click the Storage tab > Create Database > Upstash for Redis > Free plan > Create")
        say("  3. Connect it to the project (all environments)")
        say("  4. Run deploy_web.bat again")
        return 0
    say("\nYour web app is online. Open your project in https://vercel.com/dashboard to see its address")
    say("(it ends in .vercel.app)." + (f"  This upload: {url}" if url else ''))
    say(f"Friends create an account with the invite code: {state.get('invite', '(see web/.vercel/drs_setup.json)')}")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
