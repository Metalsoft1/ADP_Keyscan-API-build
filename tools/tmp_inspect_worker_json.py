import json
from pathlib import Path

OID = "G3N655VBK8E8ZAB3"  # Joshua W Bedingfield

data = json.loads(Path("output/workers.json").read_text(encoding="utf-8"))
workers = data.get("workers", [])

target = None
for w in workers:
    if (w.get("associateOID") or "").strip() == OID:
        target = w
        break

if not target:
    print("NOT FOUND:", OID)
    raise SystemExit(1)

print("Found worker keys:", sorted(list(target.keys())))

wa = target.get("workAssignments") or target.get("workAssignment") or []
print("\nworkAssignments type:", type(wa).__name__, "len:", len(wa) if isinstance(wa, list) else "n/a")

if isinstance(wa, list) and wa:
    a0 = wa[0]
    print("\nFirst assignment keys:", sorted(list(a0.keys())))
    print("\nassignmentStatus:", a0.get("assignmentStatus"))
    # print a small slice of the assignment dict for quick eyeballing
    for k in ["workAssignmentID","workAssignmentId","assignmentItemID","assignmentItemId","positionID","positionId","workerID","workerId"]:
        if k in a0:
            print(f"{k} =", a0.get(k))
else:
    print("\nNo workAssignments list found on this worker.")
