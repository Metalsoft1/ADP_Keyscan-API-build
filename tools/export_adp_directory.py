#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
import sys
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


ROOT = Path(__file__).resolve().parents[1]
CERT_CRT = ROOT / "certs" / "adp_client.crt"
CERT_KEY = ROOT / "certs" / "adp_client.key"
OUT_DIR = ROOT / "output"
OUT_CSV = OUT_DIR / "adp_directory.csv"


def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise SystemExit(f"Missing required env var: {name}")
    return val


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

    resp = session.post(
        token_url,
        data=data,
        auth=(client_id, client_secret),
        timeout=60,
    )

    if resp.status_code >= 400:
        raise SystemExit(f"Token request failed: {resp.status_code} {resp.text}")

    token = resp.json()
    if "access_token" not in token:
        raise SystemExit(f"Token missing access_token: {token}")

    return token


def adp_get_workers_page(session, workers_url, bearer, top, skip):
    params = {"$top": top, "$skip": skip}
    headers = {"Authorization": f"Bearer {bearer}", "Accept": "application/json"}

    resp = session.get(workers_url, params=params, headers=headers, timeout=90)

    if resp.status_code == 401:
        raise SystemExit(f"401 Unauthorized: {resp.text}")

    resp.raise_for_status()
    return resp.json()


def extract_worker_rows(payload):
    if isinstance(payload.get("workers"), list):
        return payload["workers"]
    return []


def flatten_worker(worker):
    associate_oid = worker.get("associateOID")

    person = worker.get("person") or {}
    legal = person.get("legalName") or {}

    given = legal.get("givenName")
    family = legal.get("familyName")
    formatted = legal.get("formattedName")

    worker_id = worker.get("workerID")

    wa_list = worker.get("workAssignments") or []
    assignment0 = wa_list[0] if wa_list else {}

    position_id = assignment0.get("positionID")
    item_id = assignment0.get("itemID")

    status_block = assignment0.get("assignmentStatus") or {}
    status_code = (status_block.get("statusCode") or {}).get("codeValue")

    payroll_file = assignment0.get("payrollFileNumber")

    return {
        "associateOID": associate_oid,
        "givenName": given,
        "familyName": family,
        "formattedName": formatted,
        "workerID": worker_id,
        "positionID": position_id,
        "itemID": item_id,
        "statusCode": status_code,
        "payrollFileNumber": payroll_file,
    }


def main():
    client_id = require_env("ADP_CLIENT_ID")
    client_secret = require_env("ADP_CLIENT_SECRET")
    token_url, workers_url = get_urls()
    cert_pair = get_cert_pair()

    top = int(os.getenv("ADP_TOP", "500"))
    max_total = int(os.getenv("ADP_MAX", "5000"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.cert = cert_pair
    session.headers.update({"User-Agent": "adp-directory-export/1.0"})

    token = request_token(session, token_url, client_id, client_secret)
    bearer = token["access_token"]

    rows: List[Dict[str, Any]] = []
    total_seen = 0
    skip = 0

    while True:
        payload = adp_get_workers_page(session, workers_url, bearer, top, skip)
        workers = extract_worker_rows(payload)

        total_seen += len(workers)
        print(f"Page: skip={skip} returned={len(workers)} total_seen={total_seen}")

        if not workers:
            break

        for w in workers:
            flat = flatten_worker(w)
            if flat.get("statusCode") == "A":
                rows.append(flat)

        if len(workers) < top:
            break

        skip += top

        if total_seen >= max_total:
            print("Reached ADP_MAX safety cap.")
            break

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    print(f"Wrote {len(rows)} active workers (total seen={total_seen})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
