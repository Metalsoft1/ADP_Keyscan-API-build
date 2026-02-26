import csv
import json
from pathlib import Path

IN_JSON = Path("output/workers_full.json")
OUT_CSV = Path("output/adp_assignment_lookup_full.csv")

data = json.loads(IN_JSON.read_text(encoding="utf-8"))
workers = data.get("workers", [])

rows = []
missing_assignments = 0
missing_itemid = 0

for w in workers:
    oid = (w.get("associateOID") or "").strip()

    # workerID is sometimes a dict; normalize to string
    worker_id = w.get("workerID")
    if isinstance(worker_id, dict):
        worker_id = worker_id.get("idValue") or worker_id.get("value") or ""
    worker_id = (str(worker_id) if worker_id is not None else "").strip()

    wa_list = w.get("workAssignments") or w.get("workAssignment") or []
    if not isinstance(wa_list, list) or not wa_list:
        missing_assignments += 1
        continue

    # Find ACTIVE assignment if present; otherwise take first
    active = None
    for a in wa_list:
        st = a.get("assignmentStatus") or {}
        sc = (st.get("statusCode") or {}).get("codeValue")
        if sc == "A":
            active = a
            break
    if active is None:
        active = wa_list[0]

    st = active.get("assignmentStatus") or {}
    status_code = (st.get("statusCode") or {}).get("codeValue") or ""

    position_id = (active.get("positionID") or active.get("positionId") or "").strip()

    item_id = active.get("itemID") or active.get("assignmentItemID") or active.get("assignmentItemId")
    item_id = (str(item_id) if item_id is not None else "").strip()
    if not item_id:
        missing_itemid += 1

    payroll_file = active.get("payrollFileNumber") or ""
    payroll_file = (str(payroll_file) if payroll_file is not None else "").strip()

    rows.append({
        "associateOID": oid,
        "workerID": worker_id,
        "statusCode": status_code,
        "positionID": position_id,
        "itemID": item_id,
        "payrollFileNumber": payroll_file,
    })

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["associateOID","workerID","statusCode","positionID","itemID","payrollFileNumber"])
    w.writeheader()
    w.writerows(rows)

print("WROTE:", OUT_CSV)
print("Workers processed:", len(workers))
print("Rows written:", len(rows))
print("Missing workAssignments:", missing_assignments)
print("Missing itemID:", missing_itemid)
