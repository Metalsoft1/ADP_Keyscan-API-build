import csv
from pathlib import Path

LOOKUP = Path("output/adp_assignment_lookup.csv")
MAP = Path("mapping/mapping.csv")

lk = { (r["associateOID"] or "").strip(): r for r in csv.DictReader(LOOKUP.open(encoding="utf-8")) }

rows = list(csv.DictReader(MAP.open(encoding="utf-8")))

print("badge,associateOID,mapping_workAssignmentItemID,lookup_itemID,MATCH")
for r in rows:
    oid = (r.get("associateOID") or "").strip()
    mid = (r.get("workAssignmentItemID") or "").strip()
    li = (lk.get(oid, {}) or {}).get("itemID","").strip()
    match = "YES" if mid and li and mid == li else ("LOOKUP_MISSING" if not li else "NO")
    print(f'{r.get("badge","")},{oid},{mid},{li},{match}')
