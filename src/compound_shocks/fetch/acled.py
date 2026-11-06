"""Download ACLED events with account credentials from the environment or .env.

The OAuth and data endpoints were verified with live Somalia and Sudan downloads on 2026-11-06.
Never log, print or raise with credentials or event rows.
"""

import os
from pathlib import Path

import pandas as pd
import requests

from compound_shocks.fetch.core import TIMEOUT_SECONDS, FetchError, get, save, sha256_of
from compound_shocks.fetch.project_env import load_project_env

TOKEN_URL = "https://acleddata.com/oauth/token"
DATA_URL = "https://acleddata.com/api/acled/read"


def fetch_acled(params: dict, out_dir: Path, root: Path | None = None) -> Path:
    load_project_env(root if root is not None else Path.cwd())
    email, password = os.environ.get("ACLED_EMAIL"), os.environ.get("ACLED_PASSWORD")
    for name, value in (("ACLED_EMAIL", email), ("ACLED_PASSWORD", password)):
        if not value:
            raise FetchError(
                f"ACLED: missing {name}. Put it in .env at the project root; "
                'see README.md "Accounts and keys". Register at https://acleddata.com, '
                'or download the file by hand as described in Getting the data.'
            )
    try:
        token = requests.post(
            TOKEN_URL,
            data={"username": email, "password": password, "grant_type": "password", "client_id": "acled"},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise FetchError(f"ACLED: login request failed ({type(exc).__name__}).") from None
    if token.status_code != 200:
        raise FetchError(f"ACLED: login failed with HTTP {token.status_code}. Check your account credentials.")
    try:
        headers = {"Authorization": f"Bearer {token.json()['access_token']}"}
        rows = get(DATA_URL, "ACLED", params={**params, "_format": "json", "limit": 0}, headers=headers).json()["data"]
    except requests.RequestException as exc:
        raise FetchError(f"ACLED: data request failed ({type(exc).__name__}).") from None
    except (KeyError, ValueError, TypeError) as exc:
        raise FetchError(f"ACLED: invalid API response ({type(exc).__name__}).") from None
    text = pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")
    return save(text, DATA_URL, Path(out_dir), f"acled_api_{sha256_of(text)[:8]}.csv")
