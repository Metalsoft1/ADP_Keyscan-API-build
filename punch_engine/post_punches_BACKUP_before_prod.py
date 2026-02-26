import json
from pathlib import Path
import yaml


def load_config():
    with open("punch_engine/config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_queue(queue_path: str):
    with open(queue_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_punch_payload_candidate(evt: dict):
    """
    Phase 2 payload:
    - Adds positionID from punch_queue.json into the outgoing candidate payload
    - Keeps workAssignmentID compatibility (workAssignmentID OR workAssignmentItemID)
    """
    return {
        "associateOID": evt.get("associateOID"),
        "workAssignmentID": evt.get("workAssignmentID") or evt.get("workAssignmentItemID"),
        "positionID": evt.get("positionID"),  # ✅ Phase 2: inject positionID
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


def main():
    cfg = load_config()
    queue_doc = load_queue(cfg["paths"]["queue_out"])
    queue = queue_doc.get("queue", [])

    dry_run = bool(cfg["engine"].get("dry_run", True))
    max_posts = int(cfg["engine"].get("max_posts_per_run", 500))

    print("POST ENGINE")
    print(f"Queue items: {len(queue)}")
    print(f"Dry run: {dry_run}")
    print("")

    if not queue:
        print("Nothing to process.")
        return

    n = min(len(queue), max_posts)

    for i, evt in enumerate(queue[:n], start=1):
        payload = build_punch_payload_candidate(evt)

        print(f"--- DRY RUN {i}/{n} ---")
        print("POST PATH (not set yet):", cfg["adp"].get("punch_post_path", ""))
        print(json.dumps(payload, indent=2))
        print("")


if __name__ == "__main__":
    main()