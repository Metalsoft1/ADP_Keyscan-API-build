import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKERS_JSON = ROOT / "output" / "workers.json"
UNMATCHED = ROOT / "output" / "unmatched_badges.csv"
OUT_MAP = ROOT / "mapping" / "mapping.csv"
OUT_STILL_UNMATCHED = ROOT / "output" / "unmatched_after_name_match.csv"

def norm_name(s: str) -> str:
    return (s or "").strip().lower()

def first_token(s: str) -> str:
    s = (s or "").strip()
    return s.split()[0].lower() if s else ""

def pick_primary_assignment(worker: dict) -> dict | None:
    wa = worker.get("workAssignments") or []
    if not isinstance(wa, list) or not wa:
        return None
    # prefer primaryIndicator
    for a in wa:
        if isinstance(a, dict) and a.get("primaryIndicator") is True:
            return a
    # otherwise first assignment
    return wa[0] if isinstance(wa[0], dict) else None

def load_workers_index():
    data = json.loads(WORKERS_JSON.read_text(encoding="utf-8"))

    # locate workers list
    workers = None
    if isinstance(data, dict):
        if "workers" in data and isinstance(data["workers"], list):
            workers = data["workers"]
        elif "workers" in data and isinstance(data["workers"], dict):
            for kk in ["worker", "workers"]:
                if kk in data["workers"] and isinstance(data["workers"][kk], list):
                    workers = data["workers"][kk]
                    break
        elif "worker" in data and isinstance(data["worker"], list):
            workers = data["worker"]

    if workers is None:
        raise RuntimeError(f"Could not find workers list in {WORKERS_JSON}")

    idx: dict[tuple[str,str], list[dict]] = {}
    for w in workers:
        if not isinstance(w, dict):
            continue
        person = (w.get("person") or {})
        legal = (person.get("legalName") or {})
        surname = norm_name(legal.get("familyName1"))
        given_first = first_token(legal.get("givenName"))

        if not surname or not given_first:
            continue

        a = pick_primary_assignment(w)
        rec = {
            "associateOID": w.get("associateOID"),
            "assignment_itemID": (a or {}).get("itemID"),
            "payrollFileNumber": (a or {}).get("payrollFileNumber"),
            "primaryIndicator": (a or {}).get("primaryIndicator"),
            "assignmentStatus": (((a or {}).get("assignmentStatus") or {}).get("statusCode") or {}).get("codeValue"),
            "full_given": legal.get("givenName"),
            "full_surname": legal.get("familyName1"),
        }
        idx.setdefault((surname, given_first), []).append(rec)
    return idx

def choose_best(cands: list[dict]) -> dict | None:
    if not cands:
        return None
    # Prefer active (A) + has IDs
    def score(c: dict) -> tuple:
        return (
            1 if c.get("assignmentStatus") == "A" else 0,
            1 if c.get("assignment_itemID") else 0,
            1 if c.get("payrollFileNumber") else 0,
        )
    return sorted(cands, key=score, reverse=True)[0]

def main():
    idx = load_workers_index()

    rows_out = []
    still_unmatched = []

    with UNMATCHED.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            badge = (r.get("badge") or "").strip()
            given = r.get("GivenName") or ""
            surname = r.get("Surname") or ""

            key = (norm_name(surname), first_token(given))
            cands = idx.get(key, [])
            best = choose_best(cands)

            if best and best.get("associateOID"):
                rows_out.append({
                    "badge": badge,
                    "associateOID": best.get("associateOID") or "",
                    "workAssignmentItemID": best.get("assignment_itemID") or "",
                    "payrollFileNumber": best.get("payrollFileNumber") or "",
                })
            else:
                still_unmatched.append({
                    "badge": badge,
                    "GivenName": given,
                    "Surname": surname,
                })

    OUT_MAP.parent.mkdir(parents=True, exist_ok=True)
    with OUT_MAP.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["badge","associateOID","workAssignmentItemID","payrollFileNumber"])
        w.writeheader()
        w.writerows(rows_out)

    if still_unmatched:
        with OUT_STILL_UNMATCHED.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["badge","GivenName","Surname"])
            w.writeheader()
            w.writerows(still_unmatched)

    print(f"DONE\nMapped: {len(rows_out)} -> {OUT_MAP.as_posix()}")
    print(f"Unmatched after name match: {len(still_unmatched)} -> {OUT_STILL_UNMATCHED.as_posix() if still_unmatched else '(none)'}")

if __name__ == "__main__":
    main()
