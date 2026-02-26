import csv, sys
from pathlib import Path

LOOKUP = Path("output/adp_assignment_lookup.csv")
MAP = Path("mapping/mapping.csv")

lk = { (r["associateOID"] or "").strip(): r for r in csv.DictReader(LOOKUP.open(encoding="utf-8")) }

failures = 0
rows = list(csv.DictReader(MAP.open(encoding="utf-8")))

print(f"Checking mapping rows: {len(rows)}\n")

for r in rows:
    badge = (r.get("badge") or "").strip()
    oid = (r.get("associateOID") or "").strip()
    mid = (r.get("workAssignmentItemID") or "").strip()

    rec = lk.get(oid)
    if not rec:
        print(f"FAIL: {badge} -> {oid} not found in ADP lookup")
        failures += 1
        continue

    li = (rec.get("itemID") or "").strip()
    status = (rec.get("statusCode") or "").strip()
    namehint = f'workerID={rec.get("workerID","")}, positionID={rec.get("positionID","")}'

    if not mid:
        print(f"FAIL: {badge} -> {oid} mapping missing workAssignmentItemID ({namehint})")
        failures += 1
        continue

    if mid != li:
        print(f"FAIL: {badge} -> {oid} mapping itemID mismatch: mapping={mid} lookup={li} ({namehint})")
        failures += 1
        continue

    if status != "A":
        print(f"FAIL: {badge} -> {oid} is not Active in ADP (statusCode={status}) ({namehint})")
        failures += 1
        continue

    print(f"OK: {badge} -> {oid} itemID={mid} status=A")

print(f"\nDONE. Failures: {failures}")
sys.exit(1 if failures else 0)
