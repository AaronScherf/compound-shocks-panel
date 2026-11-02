"""ACLED API download. Needs a free registered account; credentials come only from the environment.

The token and data endpoints follow ACLED's 2025 OAuth API and are unverified against a live call (the export
was downloaded by hand). Never log, print or raise with the credentials.
"""

import os
from pathlib import Path

import pandas as pd
import requests

from compound_shocks.fetch.core import TIMEOUT_SECONDS, FetchError, get, save, sha256_of

TOKEN_URL = "https://acleddata.com/oauth/token"
DATA_URL = "https://acleddata.com/api/acled/read"
REGISTER_HELP = (
    "ACLED data needs a free account. Register at https://acleddata.com, then set the environment variables "
    "ACLED_EMAIL and ACLED_PASSWORD (for example in a .env file that is never committed)."
)


def fetch_acled(params: dict, out_dir: Path) -> Path:
    email, password = os.environ.get("ACLED_EMAIL"), os.environ.get("ACLED_PASSWORD")
    if not email or not password:
        raise FetchError(REGISTER_HELP)
    token = requests.post(
        TOKEN_URL,
        data={"username": email, "password": password, "grant_type": "password", "client_id": "acled"},
        timeout=TIMEOUT_SECONDS,
    )
    if token.status_code != 200:
        raise FetchError(f"ACLED: login failed with HTTP {token.status_code}. Check ACLED_EMAIL and ACLED_PASSWORD.")
    headers = {"Authorization": f"Bearer {token.json()['access_token']}"}
    rows = get(DATA_URL, "ACLED", params={**params, "_format": "json", "limit": 0}, headers=headers).json()["data"]
    text = pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")
    return save(text, DATA_URL, Path(out_dir), f"acled_api_{sha256_of(text)[:8]}.csv")
