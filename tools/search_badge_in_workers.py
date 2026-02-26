import json
import re

BADGE = ".253-48810"  # <-- change this to any unmatched badge

with open(r"output/workers.json", "r", encoding="utf-8") as f:
    data = json.load(f)

raw = json.dumps(data)

print("Searching for badge:", BADGE)
print("Exact match present?", BADGE in raw)

digits = re.sub(r"\D+", "", BADGE)
print("Digits-only version:", digits)
print("Digits-only present?", digits in raw)

no_leading_zeros = digits.lstrip("0")
print("Digits no leading zeros:", no_leading_zeros)
print("Digits-no-leading-zeros present?", no_leading_zeros in raw)
