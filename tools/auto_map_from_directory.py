import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYSCAN = ROOT / "output" / "unmatched_badges.csv"   # badge + GivenName + Surname
DIRCSV  = ROOT / "output" / "adp_directory.csv"     # exported from workers.json
OUTMAP  = ROOT / "mapping" / "mapping.csv"
REVIEW  = ROOT / "output" / "needs_review.csv"
UNM2    = ROOT / "output" / "still_unmatched.csv"

def norm(s: str) -> str:
    return (s or "").strip().lower()

def first_token(s: str) -> str:
    s = (s or "").strip()
    return s.split()[0].lower() if s else ""

def score(row: dict) -> tuple:
    # higher is better
    return (
        1 if norm(row.get("assignmentStatus")) == "a" else 0,
        1 if (row.get("payrollFileNumber") or "").strip() else 0,
        1 if (row.get("assignmentItemID") or "").strip() else 0,
    )

# ---- Load ADP directory
adp = []
with DIRCSV.open("r", encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        r["_given_first"] = first_token(r.get("givenName", ""))   # removes middle initial (Jonathan W -> jonathan)
        r["_family_norm"] = norm(r.get("familyName", ""))
        adp.append(r)

mapped = []
needs_review = []
still_unmatched = []

# ---- Map Keyscan badges by (last name exact) + (first name first-token exact)
with KEYSCAN.open("r", encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        badge = (r.get("badge") or "").strip()
        g = r.get("GivenName") or ""
        s = r.get("Surname") or ""

        g1 = first_token(g)     # Keyscan first name token
        sN = norm(s)            # Keyscan last name normalized

        # 1) Exact last name match
        cands = [w for w in adp if w["_family_norm"] == sN]

        # 2) Exact first-token match (this is the middle-initial fix)
        cands2 = [w for w in cands if w["_given_first"] == g1]

        if not cands2:
            still_unmatched.append({"badge": badge, "GivenName": g, "Surname": s})
            continue

        ranked = sorted(cands2, key=score, reverse=True)
        best = ranked[0]

        # If more than 1 candidate remains, write a review list (rare, but safe)
        if len(ranked) > 1:
            for i, cand in enumerate(ranked[:3], start=1):
                needs_review.append({
                    "badge": badge,
                    "GivenName": g,
                    "Surname": s,
                    "candidate_rank": i,
                    "candidate_givenName": cand.get("givenName", ""),
                    "candidate_familyName": cand.get("familyName", ""),
                    "associateOID": cand.get("associateOID", ""),
                    "assignmentItemID": cand.get("assignmentItemID", ""),
                    "payrollFileNumber": cand.get("payrollFileNumber", ""),
                    "assignmentStatus": cand.get("assignmentStatus", ""),
                })

        mapped.append({
            "badge": badge,
            "associateOID": best.get("associateOID", ""),
            "workAssignmentItemID": best.get("assignmentItemID", ""),
            "payrollFileNumber": best.get("payrollFileNumber", ""),
        })

# ---- Write outputs
OUTMAP.parent.mkdir(parents=True, exist_ok=True)
with OUTMAP.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["badge", "associateOID", "workAssignmentItemID", "payrollFileNumber"])
    w.writeheader()
    w.writerows(mapped)

if needs_review:
    with REVIEW.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(needs_review[0].keys()))
        w.writeheader()
        w.writerows(needs_review)

if still_unmatched:
    with UNM2.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["badge", "GivenName", "Surname"])
        w.writeheader()
        w.writerows(still_unmatched)

print("DONE")
print(f"Mapped: {len(mapped)} -> {OUTMAP.as_posix()}")
print(f"Needs review rows: {len(needs_review)} -> {REVIEW.as_posix() if needs_review else '(none)'}")
print(f"Still unmatched: {len(still_unmatched)} -> {UNM2.as_posix() if still_unmatched else '(none)'}")
