import csv
from pathlib import Path

MAP = Path("mapping/mapping.csv")
LOOKUP = Path("output/adp_assignment_lookup_full.csv")

lk = {}
for r in csv.DictReader(LOOKUP.open(encoding="utf-8")):
    oid = (r.get("associateOID") or "").strip()
    if oid:
        lk[oid] = (r.get("itemID") or "").strip()

fail = 0
for r in csv.DictReader(MAP.open(encoding="utf-8")):
    badge = (r.get("badge") or "").strip()
    oid = (r.get("associateOID") or "").strip()
    mid = (r.get("workAssignmentItemID") or "").strip()

    lid = lk.get(oid, "")
    ok = (mid != "" and lid != "" and mid == lid)
    print(f"{badge},{oid},{mid},{lid},{'YES' if ok else 'NO'}")
    if not ok:
        fail += 1

print("\nDONE. Failures:", fail)
