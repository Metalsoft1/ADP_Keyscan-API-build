import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def norm(s: str) -> str:
    return str(s or "").strip().lower()


def pick_primary_work_assignment(worker: Dict[str, Any]) -> Optional[str]:
    """Return workAssignment itemID (prefer primaryIndicator=True)."""
    wa = worker.get("workAssignments") or []
    if not isinstance(wa, list) or not wa:
        return None

    for a in wa:
        if isinstance(a, dict) and a.get("primaryIndicator") is True and a.get("itemID"):
            return str(a["itemID"]).strip()

    for a in wa:
        if isinstance(a, dict) and a.get("itemID"):
            return str(a["itemID"]).strip()

    return None


def worker_status(worker: Dict[str, Any]) -> str:
    ws = worker.get("workerStatus") or {}
    sc = (ws.get("statusCode") or {}).get("codeValue")
    return str(sc or "").strip()


def is_active_worker(worker: Dict[str, Any]) -> bool:
    s = worker_status(worker).lower()
    if s in {"terminated", "t"}:
        return False
    return True


def load_workers(workers_json_path: Path, include_terminated: bool) -> List[Dict[str, Any]]:
    data = json.loads(workers_json_path.read_text(encoding="utf-8"))
    workers = data.get("workers") or []
    if not isinstance(workers, list):
        raise ValueError("workers.json does not contain a top-level 'workers' array.")

    if include_terminated:
        return [w for w in workers if isinstance(w, dict)]
    return [w for w in workers if isinstance(w, dict) and is_active_worker(w)]


def worker_name_key(worker: Dict[str, Any]) -> Tuple[str, str]:
    person = worker.get("person") or {}
    legal = person.get("legalName") or {}
    return (norm(legal.get("givenName")), norm(legal.get("familyName1")))


def build_worker_index(workers: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    idx: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for w in workers:
        key = worker_name_key(w)
        if key == ("", ""):
            continue
        idx.setdefault(key, []).append(w)
    return idx


def read_keyscan_dataset(path: Path, header_row: int) -> pd.DataFrame:
    df = pd.read_excel(path, header=header_row)

    needed = {"Credential_Number", "GivenName", "Surname"}
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Keyscan dataset missing columns: {missing}. Found columns: {list(df.columns)}")

    df["Credential_Number"] = df["Credential_Number"].astype(str).str.strip()
    df["GivenName"] = df["GivenName"].astype(str).str.strip()
    df["Surname"] = df["Surname"].astype(str).str.strip()

    df = df[df["Credential_Number"].notna() & (df["Credential_Number"].str.len() > 0)]
    return df


def unique_badges_with_names(df: pd.DataFrame) -> pd.DataFrame:
    out = (
        df[["Credential_Number", "GivenName", "Surname"]]
        .dropna()
        .drop_duplicates(subset=["Credential_Number"], keep="first")
        .rename(columns={"Credential_Number": "badge"})
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build mapping/mapping.csv from Keyscan dataset + ADP workers export")
    ap.add_argument("--dataset", default="samples/dataset.xlsx", help="Path to Keyscan dataset.xlsx")
    ap.add_argument("--workers", default="output/workers.json", help="Path to Postman-exported ADP workers JSON")
    ap.add_argument("--header-row", type=int, default=5, help="Excel header row index (0-based) for Keyscan file")
    ap.add_argument("--include-terminated", action="store_true", help="Include terminated workers from ADP export")
    ap.add_argument("--out", default="mapping/mapping.csv", help="Output mapping.csv path")
    ap.add_argument("--unmatched", default="output/unmatched_badges.csv", help="Badges we couldn't match")
    ap.add_argument("--ambiguous", default="output/ambiguous_matches.csv", help="Badges that match multiple workers")
    args = ap.parse_args()

    dataset_path = Path(args.dataset)
    workers_path = Path(args.workers)
    out_path = Path(args.out)
    unmatched_path = Path(args.unmatched)
    ambiguous_path = Path(args.ambiguous)

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    if not workers_path.exists():
        raise FileNotFoundError(f"Workers JSON not found: {workers_path} (export from Postman first)")

    keyscan_df = read_keyscan_dataset(dataset_path, header_row=args.header_row)
    badges_df = unique_badges_with_names(keyscan_df)

    workers = load_workers(workers_path, include_terminated=args.include_terminated)
    windex = build_worker_index(workers)

    mapped_rows = []
    unmatched_rows = []
    ambiguous_rows = []

    for _, r in badges_df.iterrows():
        badge = str(r["badge"]).strip()
        gn = str(r["GivenName"]).strip()
        sn = str(r["Surname"]).strip()

        key = (norm(gn), norm(sn))
        candidates = windex.get(key, [])

        if len(candidates) == 0:
            unmatched_rows.append({"badge": badge, "GivenName": gn, "Surname": sn})
            continue

        if len(candidates) > 1:
            for c in candidates:
                aoid = c.get("associateOID")
                waid = pick_primary_work_assignment(c)
                ambiguous_rows.append(
                    {
                        "badge": badge,
                        "GivenName": gn,
                        "Surname": sn,
                        "associateOID": aoid,
                        "workAssignmentID": waid,
                        "workerStatus": worker_status(c),
                    }
                )
            continue

        c = candidates[0]
        aoid = str(c.get("associateOID") or "").strip()
        waid = pick_primary_work_assignment(c) or ""
        if not aoid or not waid:
            unmatched_rows.append({"badge": badge, "GivenName": gn, "Surname": sn})
            continue

        mapped_rows.append(
            {
                "badge": badge,
                "associateOID": aoid,
                "workAssignmentID": waid,
                "GivenName": gn,
                "Surname": sn,
                "workerStatus": worker_status(c),
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_df = pd.DataFrame(mapped_rows)
    mapping_df_out = mapping_df[["badge", "associateOID", "workAssignmentID"]].copy()
    mapping_df_out.to_csv(out_path, index=False)

    if unmatched_rows:
        unmatched_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(unmatched_rows).to_csv(unmatched_path, index=False)

    if ambiguous_rows:
        ambiguous_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(ambiguous_rows).to_csv(ambiguous_path, index=False)

    print("DONE")
    print(f"Mapped: {len(mapped_rows)} -> {out_path}")
    print(f"Unmatched: {len(unmatched_rows)} -> {unmatched_path if unmatched_rows else '(none)'}")
    print(f"Ambiguous: {len(ambiguous_rows)} -> {ambiguous_path if ambiguous_rows else '(none)'}")


if __name__ == "__main__":
    main()
