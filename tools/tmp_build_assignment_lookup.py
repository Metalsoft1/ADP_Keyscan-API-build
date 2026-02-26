import json, csv
from pathlib import Path
from typing import Any

INP = Path("output/workers.json")
OUT = Path("output/adp_assignment_lookup.csv")

def as_str(v: Any) -> str:
    """Return a safe string from ADP values that might be str/dict/list/etc."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float, bool)):
        return str(v).strip()
    if isinstance(v, dict):
        # common ADP pattern: {"idValue": "..."} or {"codeValue":"..."}
        for k in ("idValue", "codeValue", "value", "name"):
            if k in v and isinstance(v[k], (str, int, float)):
                return str(v[k]).strip()
        # fallback: compact json
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        # take first scalar-ish
        for item in v:
            s = as_str(item)
            if s:
                return s
        return ""
    return str(v).strip()

data = json.loads(INP.read_text(encoding="utf-8"))
workers = data.get("workers", [])

rows = []
missing_assignments = 0
missing_itemid = 0

for w in workers:
    oid = as_str(w.get("associateOID") or w.get("associateOid"))
    worker_id = as_str(w.get("workerID") or w.get("workerId") or w.get("worker_id"))

    wa_list = w.get("workAssignments") or w.get("workAssignment") or []
    if not isinstance(wa_list, list) or not wa_list:
        missing_assignments += 1
        continue

    # find active assignment if possible
    active = None
    for wa in wa_list:
        st = wa.get("assignmentStatus") or {}
        sc = as_str((st.get("statusCode") or {}).get("codeValue"))
        if sc == "A":
            active = wa
            break
    if active is None:
        active = wa_list[0]

    st = active.get("assignmentStatus") or {}
    status_code = as_str((st.get("statusCode") or {}).get("codeValue"))

    position_id = as_str(active.get("positionID") or active.get("positionId"))
    item_id = as_str(active.get("itemID") or active.get("itemId"))
    payroll_file = as_str(active.get("payrollFileNumber"))

    if not item_id:
        missing_itemid += 1

    rows.append({
        "associateOID": oid,
        "workerID": worker_id,
        "statusCode": status_code,
        "positionID": position_id,
        "itemID": item_id,
        "payrollFileNumber": payroll_file,
    })

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["associateOID","workerID","statusCode","positionID","itemID","payrollFileNumber"])
    w.writeheader()
    w.writerows(rows)

print("WROTE:", OUT)
print("Workers processed:", len(workers))
print("Rows written:", len(rows))
print("Missing workAssignments:", missing_assignments)
print("Missing itemID:", missing_itemid)
