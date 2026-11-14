"""
Step 2: Turn NASA's messy experimental tables into ONE clean table.

Run after fetch_psi.py:   python scripts/clean.py
Output:
  data/tests.csv        one row per test run, shared columns (see FIELDS)
  data/catalog.json     investigations + our tags (safety area, fuel type, relevance)

Column detection is heuristic (NASA headers differ per experiment). Check the
printed report and fix any wrong guesses in OVERRIDES below.
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

FIELDS = ["psi_id", "acronym", "table", "row", "o2_pct", "pressure_atm",
          "airflow_cms", "fuel", "outcome", "o2_note"]

# Hand-made tags. "areas": prevention / detection / suppression.
# "fuel_kind": what burned. "crew_relevance": 1-3, how directly it maps to a
# habitat fire (solid fabrics/plastics = 3, gas/droplet flames = 2, modeling = 1).
TAGS = {
    "BASS":        {"areas": ["prevention", "suppression"], "fuel_kind": "solid", "crew_relevance": 3},
    "BASS-II":     {"areas": ["prevention", "suppression"], "fuel_kind": "solid", "crew_relevance": 3},
    "SAFFIRE-I":   {"areas": ["prevention"], "fuel_kind": "solid", "crew_relevance": 3},
    "SAFFIRE-II":  {"areas": ["prevention"], "fuel_kind": "solid", "crew_relevance": 3},
    "SAFFIRE-III": {"areas": ["prevention"], "fuel_kind": "solid", "crew_relevance": 3},
    "SAME":        {"areas": ["detection"], "fuel_kind": "smoke", "crew_relevance": 3},
    "SAME-R":      {"areas": ["detection"], "fuel_kind": "smoke", "crew_relevance": 3},
    "DAFT / DAFT-2": {"areas": ["detection"], "fuel_kind": "dust", "crew_relevance": 2},
    "FLEX":        {"areas": ["suppression"], "fuel_kind": "liquid droplet", "crew_relevance": 2},
    "FLEX-2":      {"areas": ["suppression"], "fuel_kind": "liquid droplet", "crew_relevance": 2},
    "CFI":         {"areas": ["prevention"], "fuel_kind": "liquid droplet", "crew_relevance": 1},
    "ACME BRE":    {"areas": ["prevention"], "fuel_kind": "gas (solid emulator)", "crew_relevance": 3},
    "ACME CFI-G":  {"areas": ["prevention"], "fuel_kind": "gas", "crew_relevance": 2},
    "ACME/Flame Design": {"areas": ["prevention", "detection"], "fuel_kind": "gas", "crew_relevance": 2},
    "ACME CLD Flame":    {"areas": ["prevention"], "fuel_kind": "gas", "crew_relevance": 1},
    "ACME s-Flame":      {"areas": ["prevention"], "fuel_kind": "gas", "crew_relevance": 1},
    "ACME E-FIELD Flames": {"areas": ["prevention"], "fuel_kind": "gas", "crew_relevance": 1},
    "SPICE":       {"areas": ["detection", "prevention"], "fuel_kind": "gas", "crew_relevance": 2},
    "SLICE":       {"areas": ["prevention"], "fuel_kind": "gas", "crew_relevance": 1},
}
DEFAULT_TAG = {"areas": ["prevention"], "fuel_kind": "modeling", "crew_relevance": 1}

# Force a column choice when the guess is wrong: {"PSI-69": {"o2_pct": "exact header"}}
OVERRIDES = {}


def norm(h):
    return re.sub(r"\s+", " ", h.replace("﻿", "")).strip().lower()


def pick(headers, patterns, avoid=()):
    for p in patterns:
        for h in headers:
            n = norm(h)
            if re.search(p, n) and not any(re.search(a, n) for a in avoid):
                return h
    return None


def num(x):
    if x is None:
        return None
    m = re.search(r"-?\d+(\.\d+)?", str(x).replace(",", ""))
    return float(m.group()) if m else None


def to_pct(v, header):
    if v is None:
        return None
    return v * 100 if v <= 1.0 and "%" not in header and "percent" not in norm(header) else v


def to_atm(v, header):
    if v is None:
        return None
    h = norm(header)
    if "mmhg" in h or "torr" in h:
        return v / 760
    if "kpa" in h:
        return v / 101.325
    if "psi" in h:
        return v / 14.696
    if "bar" in h:
        return v / 1.01325
    return v  # assume atm


def clean_table(inv, table_file):
    path = DATA / "tables" / table_file
    text = path.read_text(errors="replace")
    rows = list(csv.reader(text.splitlines()))
    if len(rows) < 2:
        return [], {}
    headers = rows[0]
    ov = OVERRIDES.get(inv["id"], {})
    inverse = "inverse" in table_file.lower()

    cols = {
        "o2": ov.get("o2_pct") or pick(headers, [r"percent o2", r"oxygen conc", r"o2 %", r"%.*o2",
                                                   r"xo2 \(init", r"xo2 before", r"^xo2", r"\bo\b.*initial ambient",
                                                   r"oxygen mole fraction", r"o2"],
                                       avoid=[r"final", r"after", r"co2", r"flow rate", r"mo2"]),
        "p": ov.get("pressure_atm") or pick(headers, [r"pmean", r"ambient pressure", r"pressure",
                                                      r"approx p", r"pinit", r"\bp\b.*\("]),
        "flow": ov.get("airflow_cms") or pick(headers, [r"air ?flow", r"air rate", r"inlet velocity",
                                                        r"flow velocity"]),
        "fuel": ov.get("fuel") or pick(headers, [r"material", r"^fuel$", r"fuel type", r"fuel sample",
                                                  r"sample \(fuel", r"^fuel\b", r"sample type"],
                                       avoid=[r"rate", r"mfc", r"bottle", r"conc"]),
        "outcome": ov.get("outcome") or pick(headers, [r"extinction", r"spread", r"burn length",
                                                       r"burning rate", r"flames ignited", r"cool flame",
                                                       r"self.?ext", r"burn time", r"weight loss"]),
    }

    out = []
    for i, r in enumerate(rows[1:], start=1):
        if not any(c.strip() for c in r):
            continue
        rec = dict(zip(headers, r + [""] * (len(headers) - len(r))))
        o2 = to_pct(num(rec.get(cols["o2"])), cols["o2"] or "") if cols["o2"] else None
        p = to_atm(num(rec.get(cols["p"])), cols["p"] or "") if cols["p"] else None
        notes = []
        if p is None and not cols["p"]:
            # BASS, Saffire etc. ran in normal spacecraft cabin air (~1 atm).
            p = 1.0
            notes.append("pressure assumed 1 atm (cabin air)")
        if inverse and o2 is not None:
            # Inverse flames: oxygen flows OUT of the burner, so this is burner O2, not cabin air.
            notes.append("burner O2 (inverse flame)")
        out.append({
            "psi_id": inv["id"], "acronym": inv["acronym"], "table": table_file, "row": i,
            "o2_pct": round(o2, 2) if o2 is not None else "",
            "pressure_atm": round(p, 3) if p is not None else "",
            "airflow_cms": num(rec.get(cols["flow"])) if cols["flow"] else "",
            "fuel": (rec.get(cols["fuel"]) or "").strip() if cols["fuel"] else "",
            "outcome": (rec.get(cols["outcome"]) or "").strip() if cols["outcome"] else "",
            "o2_note": "; ".join(notes),
        })
    return out, cols


def main():
    invs = json.loads((DATA / "investigations.json").read_text())
    all_rows, catalog = [], []
    print(f"{'ID':8} {'Acronym':22} rows  O2 col / pressure col / flow col")
    for inv in invs:
        tag = TAGS.get(inv["acronym"], DEFAULT_TAG)
        n_rows = 0
        for t in inv["tables"]:
            rows, cols = clean_table(inv, t["file"])
            all_rows += rows
            n_rows += len(rows)
            print(f"{inv['id']:8} {inv['acronym'][:22]:22} {len(rows):4}  "
                  f"{cols.get('o2')} / {cols.get('p')} / {cols.get('flow')}")
        catalog.append({**inv, **tag, "test_rows": n_rows})

    with open(DATA / "tests.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_rows)
    (DATA / "catalog.json").write_text(json.dumps(catalog, indent=2))
    print(f"\n{len(all_rows)} test rows -> data/tests.csv")
    print(f"{len(catalog)} investigations -> data/catalog.json")


if __name__ == "__main__":
    main()
