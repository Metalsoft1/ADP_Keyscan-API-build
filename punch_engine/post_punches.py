import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml
from requests.auth import HTTPBasicAuth


# =========================
# Config / Helpers
# =========================

def load_config():
    with open("punch_engine/config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_queue(queue_path: str):
    with open(queue_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_posted_hashes(csv_path: str) -> set[str]:
    p = Path(csv_path)
    if not p.exists():
        return set()

    out = set()
    with p.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            h = (row.get("hash") or "").strip()
            if h:
                out.add(h)
    return out


def append_posted_hash(csv_path: str, evt: dict, status_code: int):
    p = Path(csv_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    exists = p.exists()
    with p.open("a", newline="", encoding="utf-8") as f:
        fieldnames = ["posted_at_utc", "hash", "status_code", "associateOID", "badge"]
        w = csv.DictWriter(f, fieldnames=fieldnames)

        if not exists:
            w.writeheader()

        w.writerow({
            "posted_at_utc": datetime.now(timezone.utc).isoformat(),
            "hash": evt.get("hash"),
            "status_code": status_code,
            "associateOID": evt.get("associateOID"),
            "badge": evt.get("badge"),
        })


def get_mtls_cert_tuple(cfg: dict):
    """
    Returns requests-compatible cert tuple (cert_pem_path, key_pem_path) or None.
    Paths can be relative; they will be resolved relative to repo root.
    """
    cert_crt = (cfg.get("adp", {}).get("client_cert_pem") or "").strip()
    cert_key = (cfg.get("adp", {}).get("client_key_pem") or "").strip()

    if not cert_crt or not cert_key:
        return None

    # Resolve relative paths safely
    cert_crt_path = str(Path(cert_crt).expanduser().resolve())
    cert_key_path = str(Path(cert_key).expanduser().resolve())

    return (cert_crt_path, cert_key_path)


# =========================
# OAuth Token Automation
# =========================

_TOKEN_CACHE = {"access_token": None, "expires_at": 0}


def get_access_token(cfg: dict) -> str:
    now = int(time.time())

    # Reuse cached token if still valid
    if _TOKEN_CACHE["access_token"] and now < (_TOKEN_CACHE["expires_at"] - 30):
        return _TOKEN_CACHE["access_token"]

    client_id = (os.environ.get("ADP_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("ADP_CLIENT_SECRET") or "").strip()

    if not client_id or not client_secret:
        raise RuntimeError("Missing ADP_CLIENT_ID / ADP_CLIENT_SECRET environment variables")

    base_url = (cfg["adp"].get("base_url") or "").rstrip("/")
    token_url = base_url + "/auth/oauth/v2/token"

    cert = get_mtls_cert_tuple(cfg)

    resp = requests.post(
        token_url,
        auth=HTTPBasicAuth(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        timeout=float(cfg["adp"].get("timeout_seconds", 30)),
        headers={"Accept": "application/json"},
        cert=cert,  # ✅ mTLS
    )

    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"Token request failed: {resp.status_code} {resp.text[:1000]}")

    data = resp.json()
    token = (data.get("access_token") or "").strip()
    expires_in = int(data.get("expires_in") or 3600)

    if not token:
        raise RuntimeError("Token response missing access_token")

    _TOKEN_CACHE["access_token"] = token
    _TOKEN_CACHE["expires_at"] = now + expires_in

    return token


# =========================
# Payload Builder
# =========================

def build_punch_payload(evt: dict):
    return {
        "associateOID": evt.get("associateOID"),
        "workAssignmentID": evt.get("workAssignmentID") or evt.get("workAssignmentItemID"),
        "positionID": evt.get("positionID"),
        "eventTimestamp": evt.get("timestamp_iso"),
        "eventType": evt.get("event_type"),
        "source": "Keyscan",
        "reference": {
            "trans_id": evt.get("trans_id"),
            "trans_number": evt.get("trans_number"),
            "badge": evt.get("badge"),
        },
        "location": evt.get("location"),
        "idempotencyKey": evt.get("hash"),
    }


# =========================
# Main
# =========================

def main():
    cfg = load_config()

    queue_doc = load_queue(cfg["paths"]["queue_out"])
    queue = queue_doc.get("queue", [])

    dry_run = bool(cfg["engine"].get("dry_run", True))
    max_posts = int(cfg["engine"].get("max_posts_per_run", 500))

    posted_hashes_path = cfg["paths"].get("posted_hashes", "punch_engine/state/posted_hashes.csv")
    already_posted = load_posted_hashes(posted_hashes_path)

    print("POST ENGINE")
    print(f"Queue items: {len(queue)}")
    print(f"Dry run: {dry_run}")
    print(f"Already posted hashes: {len(already_posted)}")
    print("")

    if not queue:
        print("Nothing to process.")
        return

    n = min(len(queue), max_posts)

    cert = get_mtls_cert_tuple(cfg)

    token = None
    if not dry_run:
        token = get_access_token(cfg)

    ok = 0
    fail = 0
    skip = 0

    base_url = (cfg["adp"].get("base_url") or "").rstrip("/")
    post_path = cfg["adp"].get("punch_post_path", "")
    url = base_url + post_path

    for i, evt in enumerate(queue[:n], start=1):
        h = (evt.get("hash") or "").strip()

        if h in already_posted:
            skip += 1
            continue

        payload = build_punch_payload(evt)

        if dry_run:
            print(f"--- DRY RUN {i}/{n} ---")
            print(json.dumps(payload, indent=2))
            print("")
            continue

        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                data=json.dumps(payload),
                timeout=float(cfg["adp"].get("timeout_seconds", 30)),
                cert=cert,  # ✅ mTLS
            )

            if 200 <= resp.status_code < 300:
                ok += 1
                append_posted_hash(posted_hashes_path, evt, resp.status_code)
                already_posted.add(h)
            else:
                fail += 1
                print(f"FAILED {resp.status_code}: {resp.text[:1000]}")

        except Exception as e:
            fail += 1
            print(f"ERROR: {repr(e)}")

    print("SUMMARY")
    print("OK:", ok)
    print("FAILED:", fail)
    print("SKIPPED:", skip)


if __name__ == "__main__":
    main()