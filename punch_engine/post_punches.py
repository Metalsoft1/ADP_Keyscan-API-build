import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

try:
    import requests
except ImportError:
    raise SystemExit("Missing dependency: requests. Install with: pip install requests")


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


def append_posted_hash(csv_path: str, evt: dict, status_code: int, response_text: str):
    p = Path(csv_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    exists = p.exists()
    with p.open("a", newline="", encoding="utf-8") as f:
        fieldnames = ["posted_at_utc", "hash", "status_code", "associateOID", "badge", "trans_id", "trans_number"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            w.writeheader()

        w.writerow({
            "posted_at_utc": datetime.now(timezone.utc).isoformat(),
            "hash": evt.get("hash"),
            "status_code": status_code,
            "associateOID": evt.get("associateOID"),
            "badge": evt.get("badge"),
            "trans_id": evt.get("trans_id"),
            "trans_number": evt.get("trans_number"),
        })


def build_punch_payload_candidate(evt: dict):
    # Phase 2 payload: includes positionID
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


def get_bearer_token(cfg: dict) -> str:
    # default: env var
    env_name = cfg.get("adp", {}).get("bearer_token_env", "ADP_BEARER_TOKEN")
    token = (os.environ.get(env_name) or "").strip()
    if not token:
        raise RuntimeError(
            f"Missing bearer token. Set environment variable {env_name} for the account running the task."
        )
    return token


def post_one(cfg: dict, token: str, payload: dict, verify_tls=True) -> tuple[int, str]:
    base_url = (cfg["adp"].get("base_url") or "").rstrip("/")
    path = (cfg["adp"].get("punch_post_path") or "").strip()

    if not base_url:
        raise RuntimeError("config.yaml missing adp.base_url (example: https://api.adp.com)")
    if not path:
        raise RuntimeError("config.yaml missing adp.punch_post_path (example: /events/time/v2/time-entries.modify)")

    url = base_url + path

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Optional mTLS client cert:
    # adp.client_cert_pem: path to .crt or .pem
    # adp.client_key_pem:  path to .key
    cert = None
    cert_crt = (cfg["adp"].get("client_cert_pem") or "").strip()
    cert_key = (cfg["adp"].get("client_key_pem") or "").strip()
    if cert_crt and cert_key:
        cert = (cert_crt, cert_key)

    timeout_s = float(cfg["adp"].get("timeout_seconds", 30))

    resp = requests.post(
        url,
        headers=headers,
        data=json.dumps(payload),
        timeout=timeout_s,
        verify=verify_tls,
        cert=cert,
    )
    return resp.status_code, resp.text


def main():
    cfg = load_config()

    queue_doc = load_queue(cfg["paths"]["queue_out"])
    queue = queue_doc.get("queue", [])

    dry_run = bool(cfg["engine"].get("dry_run", True))
    max_posts = int(cfg["engine"].get("max_posts_per_run", 500))

    posted_hashes_path = cfg["paths"].get("posted_hashes", "output/posted_hashes.csv")
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

    token = ""
    if not dry_run:
        token = get_bearer_token(cfg)

    ok = 0
    fail = 0
    skip = 0

    for i, evt in enumerate(queue[:n], start=1):
        h = (evt.get("hash") or "").strip()
        if h and h in already_posted:
            skip += 1
            continue

        payload = build_punch_payload_candidate(evt)

        if dry_run:
            print(f"--- DRY RUN {i}/{n} ---")
            print("POST PATH:", cfg["adp"].get("punch_post_path", ""))
            print(json.dumps(payload, indent=2))
            print("")
            continue

        print(f"--- POST {i}/{n} ---")
        try:
            status, body = post_one(cfg, token, payload)
            print("Status:", status)

            if 200 <= status < 300:
                ok += 1
                append_posted_hash(posted_hashes_path, evt, status, body)
                if h:
                    already_posted.add(h)
            else:
                fail += 1
                print("Response:", body[:2000])
        except Exception as e:
            fail += 1
            print("ERROR:", repr(e))

        print("")

    print("SUMMARY")
    print("OK:", ok)
    print("FAILED:", fail)
    print("SKIPPED (already posted):", skip)
    print("posted_hashes:", posted_hashes_path)


if __name__ == "__main__":
    main()