import csv
from pathlib import Path

p = Path("output/adp_directory.csv")
rows = list(csv.DictReader(p.open(encoding="utf-8")))
total = len(rows)

pf_vals = [ (r.get("payrollFileNumber") or "").strip() for r in rows ]
wid_vals = [ (r.get("workerID") or "").strip() for r in rows ]

pf = sum(1 for v in pf_vals if v)
wid = sum(1 for v in wid_vals if v)

def sample(vals, n=10):
    out = []
    for v in vals:
        if v and v not in out:
            out.append(v)
        if len(out) >= n:
            break
    return out

print("Rows:", total)
print("payrollFileNumber populated:", pf)
print("workerID populated:", wid)
print("Sample payrollFileNumber:", sample(pf_vals))
print("Sample workerID:", sample(wid_vals))
