import csv
from pathlib import Path

adp = list(csv.DictReader(Path("output/adp_directory.csv").open(encoding="utf-8")))
adp_by_oid = { (r.get("associateOID") or "").strip(): r for r in adp }

m = list(csv.DictReader(Path("mapping/mapping.csv").open(encoding="utf-8")))

bad = 0
print("Checking mapping rows:", len(m))
print()

for row in m:
    badge = row.get("badge","").strip()
    oid = row.get("associateOID","").strip()
    witem = row.get("workAssignmentItemID","").strip()
    pf = (row.get("payrollFileNumber") or "").strip()

    adp_row = adp_by_oid.get(oid)
    if not adp_row:
        bad += 1
        print(f"FAIL: badge {badge} -> associateOID {oid} not found in ACTIVE ADP directory (may be terminated or missing).")
        continue

    # Validate assignmentItemID
    adp_item = (adp_row.get("assignmentItemID") or "").strip()
    if adp_item and witem and adp_item != witem:
        bad += 1
        print(f"FAIL: badge {badge} oid {oid} assignmentItem mismatch: mapping={witem} adp={adp_item}")

    # Validate payrollFileNumber (if populated in ADP export)
    adp_pf = (adp_row.get("payrollFileNumber") or "").strip()
    if adp_pf and pf and adp_pf != pf:
        bad += 1
        print(f"FAIL: badge {badge} oid {oid} payrollFileNumber mismatch: mapping={pf} adp={adp_pf}")

    # If passes
    if adp_item == witem or not adp_item:
        print(f"OK: {badge} -> {adp_row.get('formattedName')} ({oid})")

print()
print("DONE. Failures:", bad)
