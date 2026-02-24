import csv
from pathlib import Path
from collections import defaultdict, Counter

ADP_CSV = Path("output/adp_directory.csv")
KS_CSV  = Path("samples/keyscan_export.csv")
MAP_CSV = Path("mapping/mapping.csv")

OUT_SUG = Path("mapping/mapping_suggestions.csv")
OUT_AMB = Path("output/mapping_ambiguous.csv")
OUT_UNM = Path("output/mapping_unmatched_names.csv")

def norm(s: str) -> str:
    return (s or "").strip().lower()

def parse_formatted_name(s: str):
    # "Last, First Middle" -> (first, last)
    s = (s or "").strip()
    if "," in s:
        last, rest = s.split(",", 1)
        last = last.strip()
        first = rest.strip().split(" ")[0].strip() if rest.strip() else ""
        return first, last
    return "", ""

# --- Load existing mapped badges (so we only suggest new ones) ---
mapped_badges = set()
for r in csv.DictReader(MAP_CSV.open(encoding="utf-8")):
    b = (r.get("badge") or "").strip()
    if b:
        mapped_badges.add(b)

# --- Load ADP actives and build name index ---
adp_rows = list(csv.DictReader(ADP_CSV.open(encoding="utf-8")))
adp_people = []
for r in adp_rows:
    first = (r.get("givenName") or "").strip()
    last  = (r.get("familyName") or "").strip()
    if not first or not last:
        f2, l2 = parse_formatted_name(r.get("formattedName") or "")
        if not first: first = f2
        if not last:  last  = l2

    key = (norm(first), norm(last))
    adp_people.append({
        "key": key,
        "associateOID": (r.get("associateOID") or "").strip(),
        "workAssignmentItemID": (r.get("assignmentItemID") or "").strip(),
        "payrollFileNumber": (r.get("payrollFileNumber") or "").strip(),
        "formattedName": (r.get("formattedName") or "").strip(),
        "givenName": first,
        "familyName": last,
    })

adp_by_name = defaultdict(list)
for p in adp_people:
    adp_by_name[p["key"]].append(p)

# --- Load Keyscan events: build badge(s) per name, but only for UNMAPPED badges ---
ks_rows = list(csv.DictReader(KS_CSV.open(encoding="utf-8")))
badges_by_name = defaultdict(list)
events_by_name = Counter()

for r in ks_rows:
    badge = (r.get("Credential_Number") or "").strip()
    if not badge or badge in mapped_badges:
        continue

    first = norm(r.get("GivenName") or "")
    last  = norm(r.get("Surname") or "")
    if not first or not last:
        continue

    key = (first, last)
    badges_by_name[key].append(badge)
    events_by_name[key] += 1

# --- Decide safe vs ambiguous vs unmatched ---
OUT_SUG.parent.mkdir(parents=True, exist_ok=True)
OUT_AMB.parent.mkdir(parents=True, exist_ok=True)
OUT_UNM.parent.mkdir(parents=True, exist_ok=True)

suggest = []
ambig = []
unmatched = []

for key, badges in sorted(badges_by_name.items(), key=lambda kv: events_by_name[kv[0]], reverse=True):
    first, last = key
    uniq_badges = sorted(set(badges))
    adp_matches = adp_by_name.get(key, [])

    if len(adp_matches) == 0:
        unmatched.append({
            "GivenName": first,
            "Surname": last,
            "keyscan_event_count": events_by_name[key],
            "unique_badges": "|".join(uniq_badges),
        })
        continue

    if len(adp_matches) > 1:
        ambig.append({
            "reason": "MULTIPLE_ADP_MATCHES_SAME_NAME",
            "GivenName": first,
            "Surname": last,
            "keyscan_event_count": events_by_name[key],
            "keyscan_unique_badges": "|".join(uniq_badges),
            "adp_matches": "|".join([f'{m["formattedName"]} ({m["associateOID"]})' for m in adp_matches]),
        })
        continue

    if len(uniq_badges) != 1:
        ambig.append({
            "reason": "MULTIPLE_KEYSCAN_BADGES_FOR_NAME",
            "GivenName": first,
            "Surname": last,
            "keyscan_event_count": events_by_name[key],
            "keyscan_unique_badges": "|".join(uniq_badges),
            "adp_match": f'{adp_matches[0]["formattedName"]} ({adp_matches[0]["associateOID"]})',
        })
        continue

    # SAFE suggestion
    b = uniq_badges[0]
    m = adp_matches[0]
    suggest.append({
        "badge": b,
        "associateOID": m["associateOID"],
        "workAssignmentItemID": m["workAssignmentItemID"],
        "payrollFileNumber": m["payrollFileNumber"],
        "adp_formattedName": m["formattedName"],
        "keyscan_event_count": events_by_name[key],
    })

# Write outputs
with OUT_SUG.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["badge","associateOID","workAssignmentItemID","payrollFileNumber","adp_formattedName","keyscan_event_count"])
    w.writeheader()
    w.writerows(suggest)

with OUT_AMB.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["reason","GivenName","Surname","keyscan_event_count","keyscan_unique_badges","adp_matches","adp_match"])
    w.writeheader()
    w.writerows(ambig)

with OUT_UNM.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["GivenName","Surname","keyscan_event_count","unique_badges"])
    w.writeheader()
    w.writerows(unmatched)

print("DONE")
print("Existing mapped badges:", len(mapped_badges))
print("Suggestions (safe):", len(suggest), "->", OUT_SUG)
print("Ambiguous:", len(ambig), "->", OUT_AMB)
print("Unmatched names:", len(unmatched), "->", OUT_UNM)
