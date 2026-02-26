import os
import json
from datetime import datetime, timezone
import requests

BASE_URL = os.getenv("ADP_BASE_URL", "https://api.adp.com").rstrip("/")
TOKEN = os.getenv("ADP_ACCESS_TOKEN", "").strip()

CERT_PEM = os.getenv("ADP_MTLS_CERT_PEM", "").strip()
KEY_PEM  = os.getenv("ADP_MTLS_KEY_PEM", "").strip()
VERIFY   = os.getenv("ADP_VERIFY", "true").strip().lower()

POST_PATH = "/events/time/v1/data-collection-entries.process"

def parse_verify(v: str):
    if v in ("true", "1", "yes"):
        return True
    if v in ("false", "0", "no"):
        return False
    return v

def to_utc_iso(ts: str) -> str:
    # Input like: 2026-01-15T14:05:31-06:00
    dt = datetime.fromisoformat(ts)
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")

def main():
    if not TOKEN:
        raise SystemExit("Missing ADP_ACCESS_TOKEN")
    if not (CERT_PEM and KEY_PEM):
        raise SystemExit("Missing ADP_MTLS_CERT_PEM / ADP_MTLS_KEY_PEM")

    # Load queue
    with open(r"output/punch_queue.json", "r", encoding="utf-8") as f:
        d = json.load(f)

    q = d.get("queue", [])
    if not q:
        raise SystemExit("Queue empty")

    e = q[0]

    # Map IN/OUT to ADP action (we’ll adjust if ADP wants different codes)
    direction = (e.get("event_type") or "").strip().upper()
    if direction not in ("IN", "OUT"):
        raise SystemExit(f"Unsupported event_type: {direction}")

    # Build a conservative payload
    # NOTE: Field names may differ slightly; if ADP rejects, we’ll tune based on response.
    payload = {
        "events": [
            {
                "eventDateTime": to_utc_iso(e["timestamp_iso"]),
                "eventTypeCode": {"codeValue": direction},  # may need different codeValue; we’ll learn from response
                "worker": {"associateOID": e["associateOID"]},
                "workAssignment": {"workAssignmentID": e["workAssignmentItemID"]},
                "externalID": e.get("hash") or e.get("trans_id") or e.get("trans_number"),
            }
        ]
    }

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    url = f"{BASE_URL}{POST_PATH}"
    verify = parse_verify(VERIFY)

    os.makedirs("output", exist_ok=True)
    with open("output/last_post_request.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    r = requests.post(url, headers=headers, json=payload, cert=(CERT_PEM, KEY_PEM), verify=verify, timeout=60)

    print("POST", url)
    print("Status:", r.status_code)

    out_resp = "output/last_post_response.json"
    try:
        data = r.json()
        with open(out_resp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print("Saved:", out_resp)
        print("Top-level keys:", list(data.keys())[:25])
    except ValueError:
        with open(out_resp, "w", encoding="utf-8") as f:
            f.write(r.text)
        print("Saved (non-JSON):", out_resp)
        print("Body preview:", r.text[:500])

if __name__ == "__main__":
    main()