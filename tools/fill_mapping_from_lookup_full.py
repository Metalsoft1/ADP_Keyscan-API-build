import csv
from pathlib import Path

MAP = Path("mapping/mapping.csv")
LOOKUP = Path("output/adp_assignment_lookup_full.csv")
OUT = Path("mapping/mapping.csv")  # in-place update (safe if you backup first)

# --- Load lookup by associateOID ---
lk = {}
for r in csv.DictReader(LOOKUP.open(encoding="utf-8")):
    oid = (r.get("associateOID") or "").strip()
    if not oid:
        continue
    lk[oid] = {
        "itemID": (r.get("itemID") or "").strip(),
        "payrollFileNumber": (r.get("payrollFileNumber") or "").strip(),
        "statusCode": (r.get("statusCode") or "").strip(),
        "positionID": (r.get("positionID") or "").strip(),
    }

rows = list(csv.DictReader(MAP.open(encoding="utf-8")))
updated_item = 0
updated_pf = 0
missing_in_lookup = 0

for r in rows:
    oid = (r.get("associateOID") or "").strip()
    if not oid:
        continue

    hit = lk.get(oid)
    if not hit:
        missing_in_lookup += 1
        continue

    # Fill itemID if missing
    if not (r.get("workAssignmentItemID") or "").strip() and hit["itemID"]:
        r["workAssignmentItemID"] = hit["itemID"]
        updated_item += 1

    # Fill payrollFileNumber if missing
    if not (r.get("payrollFileNumber") or "").strip() and hit["payrollFileNumber"]:
        r["payrollFileNumber"] = hit["payrollFileNumber"]
        updated_pf += 1

# Write back
with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["badge","associateOID","workAssignmentItemID","payrollFileNumber"])
    w.writeheader()
    w.writerows(rows)

print("DONE")
print("Rows updated workAssignmentItemID:", updated_item)
print("Rows updated payrollFileNumber:", updated_pf)
print("Mapping rows missing from lookup:", missing_in_lookup)
