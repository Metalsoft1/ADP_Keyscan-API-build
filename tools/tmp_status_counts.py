import json
from collections import Counter
from pathlib import Path

p = Path("output/workers.json")
data = json.loads(p.read_text(encoding="utf-8"))
workers = data.get("workers", [])
print("Workers in JSON:", len(workers))

def status_codes_for_worker(w):
    codes = []
    for wa in (w.get("workAssignments") or []):
        st = wa.get("assignmentStatus") or {}
        sc = st.get("statusCode") or {}
        code = sc.get("codeValue")
        if code:
            codes.append(code)
    return codes

c_all = Counter()
any_active = 0
all_terminated = 0
missing = 0

for w in workers:
    codes = status_codes_for_worker(w)
    if not codes:
        missing += 1
        continue

    for code in codes:
        c_all[code] += 1

    if "A" in codes:
        any_active += 1
    if all(code == "T" for code in codes):
        all_terminated += 1

print("\nAssignment status code counts across ALL assignments:")
for k, v in c_all.most_common():
    print(f"  {k}: {v}")

print(f"\nWorkers with ANY Active assignment (has 'A'): {any_active}")
print(f"Workers where ALL assignments are Terminated ('T' only): {all_terminated}")
print(f"Workers with no assignmentStatus codes: {missing}")
