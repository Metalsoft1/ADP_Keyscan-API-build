import csv
import json
import hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

import yaml  # pip install pyyaml


def load_config():
    with open("punch_engine/config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def read_mapping(mapping_csv_path: str):
    """
    mapping.csv expected columns (Phase 2):
      badge,associateOID,workAssignmentItemID,payrollFileNumber,positionID

    Backward-compatible:
      - also accepts workAssignmentID
    """
    mapping = {}
    with open(mapping_csv_path, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            badge = (row.get("badge") or "").strip()
            aoid = (row.get("associateOID") or "").strip()
            waid = (row.get("workAssignmentItemID") or row.get("workAssignmentID") or "").strip()
            posid = (row.get("positionID") or "").strip()

            # keep existing requirement: badge + aoid + work assignment
            if badge and aoid and waid:
                mapping[badge] = {
                    "associateOID": aoid,
                    "workAssignmentID": waid,   # internal name unchanged
                    "positionID": posid,        # ✅ store positionID
                }
    return mapping


def load_posted_hashes(posted_hashes_path: str):
    path = Path(posted_hashes_path)
    if not path.exists():
        return set()
    hashes = set()
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            h = (row.get("hash") or "").strip()
            if h:
                hashes.add(h)
    return hashes


def parse_keyscan_rows(keyscan_csv_path: str):
    with open(keyscan_csv_path, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        return list(r)


def build_event(row: dict, tz: ZoneInfo):
    """
    Keyscan columns (from your sample):
    Credential_Number -> badge
    DateTime          -> timestamp ("YYYY-MM-DD HH:MM:SS")
    Location          -> contains "(In)" or "(Out)"
    """
    badge = (row.get("Credential_Number") or "").strip()
    ts_raw = (row.get("DateTime") or "").strip()
    location = (row.get("Location") or "").strip()
    trans_id = (row.get("ID") or "").strip()
    trans_number = (row.get("TransNumber") or "").strip()

    if not badge or not ts_raw:
        return None

    try:
        dt = datetime.strptime(ts_raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
    except ValueError:
        return {"_error": "unparsed_timestamp", "badge": badge, "timestamp_raw": ts_raw, "row": row}

    loc_upper = location.upper()
    if "(IN)" in loc_upper:
        etype = "IN"
    elif "(OUT)" in loc_upper:
        etype = "OUT"
    else:
        etype = "PUNCH"

    return {
        "badge": badge,
        "timestamp_iso": dt.isoformat(),
        "event_type": etype,
        "location": location,
        "trans_id": trans_id,
        "trans_number": trans_number,
        "_raw": row,
    }


def main():
    cfg = load_config()
    tz = ZoneInfo(cfg["engine"]["timezone"])

    mapping = read_mapping(cfg["paths"]["mapping_csv"])
    posted = load_posted_hashes(cfg["paths"]["posted_hashes"])

    rows = parse_keyscan_rows(cfg["paths"]["keyscan_csv"])

    now = datetime.now(tz)
    lookback = now - timedelta(minutes=int(cfg["engine"]["lookback_minutes"]))

    queue = []
    errors = []
    skipped_unmapped = 0
    skipped_old = 0
    skipped_dupe = 0

    for row in rows:
        event = build_event(row, tz)
        if not event:
            continue

        if "_error" in event:
            errors.append(event)
            continue

        ts = datetime.fromisoformat(event["timestamp_iso"])
        if ts < lookback:
            skipped_old += 1
            continue

        badge = event["badge"]
        m = mapping.get(badge)
        if not m:
            skipped_unmapped += 1
            continue

        event["associateOID"] = m["associateOID"]
        event["workAssignmentItemID"] = m["workAssignmentID"]

        # ✅ Phase 2: inject positionID into queued event
        event["positionID"] = m.get("positionID", "")

        h = sha256_hex(
            f'{event["associateOID"]}|{event.get("positionID","")}|{event.get("workAssignmentItemID","")}|{event["timestamp_iso"]}|{event["event_type"]}|{event.get("location","")}|{event.get("trans_id","")}'
        )
        event["hash"] = h

        if h in posted:
            skipped_dupe += 1
            continue

        queue.append(event)

    out_path = Path(cfg["paths"]["queue_out"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"generated_at": now.isoformat(), "queue": queue, "errors": errors}, indent=2),
        encoding="utf-8",
    )

    print("DONE")
    print(f"Rows read: {len(rows)}")
    print(f"Queue size: {len(queue)}")
    print(f"Errors: {len(errors)}")
    print(f"Skipped old (lookback): {skipped_old}")
    print(f"Skipped unmapped badge: {skipped_unmapped}")
    print(f"Skipped already-posted hash: {skipped_dupe}")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()