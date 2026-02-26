import json

with open(r"output/punch_queue.json", "r", encoding="utf-8") as f:
    d = json.load(f)

q = d.get("queue", [])

print("Queue size:", len(q))

if not q:
    raise SystemExit("Queue empty")

missing_pos = sum(1 for e in q if not (e.get("positionID") or "").strip())
print("Missing positionID:", missing_pos, "of", len(q))

print("\nFirst event keys:")
for k in sorted(q[0].keys()):
    print(" -", k)

print("\nFirst event positionID:", q[0].get("positionID"))

# ADD THIS PART
print("\nFirst event full (sanitized):")

e0 = q[0].copy()
e0.pop("_raw", None)
print(json.dumps(e0, indent=2))
