import csv
from pathlib import Path
from collections import Counter

ks = list(csv.DictReader(Path("samples/keyscan_export.csv").open(encoding="utf-8")))
mapped = set()

for r in csv.DictReader(Path("mapping/mapping.csv").open(encoding="utf-8")):
    b = (r.get("badge") or "").strip()
    if b:
        mapped.add(b)

badge_counts = Counter()
for r in ks:
    b = (r.get("Credential_Number") or "").strip()
    if b:
        badge_counts[b] += 1

unmapped = [(b,c) for b,c in badge_counts.most_common() if b not in mapped]

print("Mapped badges:", len(mapped))
print("Badges seen in Keyscan export:", len(badge_counts))
print("Unmapped badges seen:", len(unmapped))
print()
print("Top 30 unmapped badges by event count:")
for b,c in unmapped[:30]:
    print(f"{b},{c}")
