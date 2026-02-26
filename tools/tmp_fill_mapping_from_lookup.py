import csv
from pathlib import Path

LOOKUP = Path("output/adp_assignment_lookup.csv")
MAP = Path("mapping/mapping.csv")

# build lookup by associateOID
lk = {}
for r in csv.DictReader(LOOKUP.open(encoding="utf-8")):
    oid = (r.get("associateOID") or "").strip()
    if oid:
        lk[oid] = r

rows = list(csv.DictReader(MAP.open(encoding="utf-8")))

updated = 0
missing = 0

for r in rows:
    oid = (r.get("associateOID") or "").strip()
    if not oid:
        continue
    if oid not in lk:
        missing += 1
        continue

    # only fill blanks (don't overwrite your existing 4 yet)
    if not (r.get("workAssignmentItemID") or "").strip():
        r["workAssignmentItemID"] = (lk[oid].get("itemID") or "").strip()
        updated += 1

    if not (r.get("payrollFileNumber") or "").strip():
        r["payrollFileNumber"] = (lk[oid].get("payrollFileNumber") or "").strip()

# write back
with MAP.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["badge","associateOID","workAssignmentItemID","payrollFileNumber"])
    w.writeheader()
    w.writerows(rows)

print("DONE")
print("Rows updated with itemID:", updated)
print("Mapping rows missing from lookup:", missing)
