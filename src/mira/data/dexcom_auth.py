"""One-time Dexcom OAuth setup.

Run once to obtain a refresh token:

    python -m mira.data.dexcom_auth

Steps it walks you through:
  1. Open the printed URL in a browser.
  2. Log in as a Dexcom sandbox user (e.g. SandboxUser1) and consent.
  3. You'll be redirected to your redirect URI with a `?code=...` on the URL.
  4. Paste that full redirected URL back here.

It prints the refresh token to store as DEXCOM_REFRESH_TOKEN in your .env.
"""

import os
import sys
import urllib.parse
import webbrowser

import requests

from mira.config import load_env


def _require(name):
    val = os.environ.get(name)
    if not val:
        sys.exit(f"Missing {name}. Set it in your environment or .env first.")
    return val


def main():
    load_env()
    base_url = (os.environ.get("DEXCOM_BASE_URL")
                or "https://sandbox-api.dexcom.com").rstrip("/")
    client_id = _require("DEXCOM_CLIENT_ID")
    client_secret = _require("DEXCOM_CLIENT_SECRET")
    redirect_uri = _require("DEXCOM_REDIRECT_URI")

    authorize_url = f"{base_url}/v2/oauth2/login?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "offline_access",
    })

    print("\n1. Open this URL and log in as a sandbox user:\n")
    print("   " + authorize_url + "\n")
    try:
        webbrowser.open(authorize_url)
    except Exception:
        pass  # headless environments: user opens it manually

    print("2. After consenting you'll be redirected to your redirect URI.")
    redirected = input("3. Paste the full redirected URL (or just the code): ").strip()

    code = redirected
    if "code=" in redirected:
        query = urllib.parse.urlparse(redirected).query
        code = urllib.parse.parse_qs(query).get("code", [""])[0]
    if not code:
        sys.exit("Could not find an authorization code in that input.")

    resp = requests.post(
        f"{base_url}/v2/oauth2/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=15,
    )
    if not resp.ok:
        sys.exit(f"Token exchange failed ({resp.status_code}): {resp.text}")

    tokens = resp.json()
    print("\nSuccess. Add this line to your .env:\n")
    print(f"DEXCOM_REFRESH_TOKEN={tokens['refresh_token']}\n")


if __name__ == "__main__":
    main()
