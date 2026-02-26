import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKERS_JSON = ROOT / "output" / "workers.json"
UNMATCHED = ROOT / "output" / "unmatched_badges.csv"
OUT_MAP = ROOT / "mapping" / "mapping.csv"
OUT_STILL_UNMATCHED = ROOT / "output" / "unmatched_after_fuzzy_match.csv"

def norm(s: str) -> str:
    return (s or "").strip().lower()

def first_token(s: str) -> str:
    s = (s or "").strip()
    return s.split()[0].lower() if s else ""

def pick_primary_assignment(worker: dict) -> dict | None:
    wa = worker.get("workAssignments") or []
    if not isinstance(wa, list) or not wa:
        return None
    for a in wa:
        if isinstance(a, dict) and a.get("primaryIndicator") is True:
            return a
    return wa[0] if isinstance(wa[0], dict) else None

def score(candidate: dict) -> tuple:
    # higher is better
    return (
        1 if candidate.get("assignmentStatus") == "A" else 0,
        1 if candidate.get("primaryIndicator") else 0,
        1 if candidate.get("assignment_itemID") else 0,
        1 if candidate.get("payrollFileNumber") else 0,
    )

def load_workers():
    data = json.loads(WORKERS_JSON.read_text(encoding="utf-8"))

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

    out = []
    for w in workers:
        if not isinstance(w, dict):
            continue
        person = (w.get("person") or {})
        legal = (person.get("legalName") or {})
        given = legal.get("givenName") or ""
        surname = legal.get("familyName1") or ""
        formatted = legal.get("formattedName") or ""

        a = pick_primary_assignment(w)
        out.append({
            "associateOID": w.get("associateOID"),
            "given": given,
            "surname": surname,
            "formatted": formatted,
            "given_first": first_token(given),
            "surname_norm": norm(surname),
            "blob": norm(json.dumps(w)),  # for contains searching if needed
            "assignment_itemID": (a or {}).get("itemID"),
            "payrollFileNumber": (a or {}).get("payrollFileNumber"),
            "primaryIndicator": (a or {}).get("primaryIndicator"),
            "assignmentStatus": (((a or {}).get("assignmentStatus") or {}).get("statusCode") or {}).get("codeValue"),
        })
    return out

def main():
    workers = load_workers()

    rows_out = []
    still = []

    with UNMATCHED.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            badge = (r.get("badge") or "").strip()
            g = r.get("GivenName") or ""
            s = r.get("Surname") or ""
            g1 = first_token(g)
            sN = norm(s)

            # fuzzy candidates:
            cands = []
            for w in workers:
                # surname exact OR contained
                if sN and (w["surname_norm"] == sN or sN in w["surname_norm"] or sN in w["blob"]):
                    # given name token contained
                    if g1 and (g1 == w["given_first"] or g1 in norm(w["given"]) or g1 in w["blob"]):
                        cands.append(w)

            if not cands:
                still.append({"badge": badge, "GivenName": g, "Surname": s})
                continue

            best = sorted(cands, key=score, reverse=True)[0]
            rows_out.append({
                "badge": badge,
                "associateOID": best.get("associateOID") or "",
                "workAssignmentItemID": best.get("assignment_itemID") or "",
                "payrollFileNumber": best.get("payrollFileNumber") or "",
            })

    OUT_MAP.parent.mkdir(parents=True, exist_ok=True)
    with OUT_MAP.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["badge","associateOID","workAssignmentItemID","payrollFileNumber"])
        w.writeheader()
        w.writerows(rows_out)

    if still:
        with OUT_STILL_UNMATCHED.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["badge","GivenName","Surname"])
            w.writeheader()
            w.writerows(still)

    print(f"DONE\nMapped: {len(rows_out)} -> {OUT_MAP.as_posix()}")
    print(f"Unmatched after fuzzy match: {len(still)} -> {OUT_STILL_UNMATCHED.as_posix() if still else '(none)'}")

if __name__ == "__main__":
    main()

