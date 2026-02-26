#!/usr/bin/env python3
"""
Export ALL workers from ADP HR/v2/workers into output/workers_full.json
with paging ($top/$skip) using mTLS + OAuth client credentials.

Required env vars:
  ADP_CLIENT_ID
  ADP_CLIENT_SECRET

Optional:
  ADP_TOKEN_URL   default https://api.adp.com/auth/oauth/v2/token
  ADP_WORKERS_URL default https://api.adp.com/hr/v2/workers
  ADP_SCOPE       default api
  ADP_TOP         default 100
  ADP_MAX         default 20000  (safety cap)
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

ROOT = Path(__file__).resolve().parents[1]
CERT_CRT = ROOT / "certs" / "adp_client.crt"
CERT_KEY = ROOT / "certs" / "adp_client.key"

OUT_DIR = ROOT / "output"
OUT_JSON = OUT_DIR / "workers_full.json"


def require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v


def get_urls() -> Tuple[str, str]:
    token_url = os.getenv("ADP_TOKEN_URL", "https://api.adp.com/auth/oauth/v2/token")
    workers_url = os.getenv("ADP_WORKERS_URL", "https://api.adp.com/hr/v2/workers")
    return token_url, workers_url


def get_cert_pair() -> Tuple[str, str]:
    if not CERT_CRT.exists():
        raise SystemExit(f"Missing cert file: {CERT_CRT}")
    if not CERT_KEY.exists():
        raise SystemExit(f"Missing key file: {CERT_KEY}")
    return str(CERT_CRT), str(CERT_KEY)


def request_token(session: requests.Session, token_url: str, client_id: str, client_secret: str) -> Dict[str, Any]:
    scope = os.getenv("ADP_SCOPE", "api")
    data = {"grant_type": "client_credentials", "scope": scope}
    resp = session.post(token_url, data=data, auth=(client_id, client_secret), timeout=60)

    if resp.status_code >= 400:
        raise SystemExit(f"Token request failed.\nStatus: {resp.status_code}\nBody: {resp.text}")

    tok = resp.json()
    if "access_token" not in tok:
        raise SystemExit(f"Token response missing access_token: {tok}")
    return tok


def adp_get_page(session: requests.Session, workers_url: str, bearer: str, top: int, skip: int) -> Dict[str, Any]:
    params = {"$top": top, "$skip": skip}
    headers = {"Authorization": f"Bearer {bearer}", "Accept": "application/json"}
    resp = session.get(workers_url, params=params, headers=headers, timeout=90)

    if resp.status_code == 401:
        raise SystemExit(f"401 Unauthorized.\nURL: {resp.url}\nBody: {resp.text}")

    resp.raise_for_status()
    return resp.json()


def extract_workers(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    # common case observed in your data: {"workers": [ ... ]}
    w = payload.get("workers")
    if isinstance(w, list):
        return w
    # fallbacks (just in case)
    if isinstance(w, dict) and isinstance(w.get("worker"), list):
        return w["worker"]
    for k in ("items", "data"):
        if isinstance(payload.get(k), list):
            return payload[k]
    return []


def main() -> int:
    client_id = require_env("ADP_CLIENT_ID")
    client_secret = require_env("ADP_CLIENT_SECRET")
    token_url, workers_url = get_urls()
    cert_pair = get_cert_pair()

    top = int(os.getenv("ADP_TOP", "100"))
    max_total = int(os.getenv("ADP_MAX", "20000"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.cert = cert_pair
    session.headers.update({"User-Agent": "adp-workers-export/1.0"})

    token = request_token(session, token_url, client_id, client_secret)
    bearer = token["access_token"]
    expires_in = int(token.get("expires_in", 3600))
    deadline = time.time() + max(0, expires_in - 60)

    all_workers: List[Dict[str, Any]] = []
    skip = 0
    total_seen = 0

    while True:
        if total_seen >= max_total:
            print(f"Reached ADP_MAX safety cap ({max_total}). Stopping.")
            break

        if time.time() >= deadline:
            token = request_token(session, token_url, client_id, client_secret)
            bearer = token["access_token"]
            expires_in = int(token.get("expires_in", 3600))
            deadline = time.time() + max(0, expires_in - 60)

        payload = adp_get_page(session, workers_url, bearer, top=top, skip=skip)
        workers = extract_workers(payload)

        total_seen += len(workers)
        print(f"Page: skip={skip} returned={len(workers)} total_seen={total_seen}")

        if not workers:
            break

        all_workers.extend(workers)

        if len(workers) < top:
            break

        skip += top

    OUT_JSON.write_text(json.dumps({"workers": all_workers}, indent=2), encoding="utf-8")
    print(f"Wrote workers_full.json with workers={len(all_workers)} -> {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
