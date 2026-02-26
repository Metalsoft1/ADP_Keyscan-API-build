import csv
from pathlib import Path

src = Path("mapping/mapping_suggestions.csv")
dst = Path("mapping/mapping.csv")

existing = set()
rows = list(csv.DictReader(dst.open(encoding="utf-8")))
for r in rows:
    existing.add((r.get("badge","").strip(), r.get("associateOID","").strip()))

new_rows = []
for r in csv.DictReader(src.open(encoding="utf-8")):
    key = (r.get("badge","").strip(), r.get("associateOID","").strip())
    if key in existing:
        continue
    new_rows.append({
        "badge": r.get("badge","").strip(),
        "associateOID": r.get("associateOID","").strip(),
        "workAssignmentItemID": "",     # fill later from workers.json once we find correct field
        "payrollFileNumber": "",        # your ADP export shows blank anyway
    })

out = rows + new_rows

with dst.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["badge","associateOID","workAssignmentItemID","payrollFileNumber"])
    w.writeheader()
    w.writerows(out)

print(f"Appended {len(new_rows)} rows into {dst}")
