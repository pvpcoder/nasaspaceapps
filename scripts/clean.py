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
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profiles import PROFILES  # noqa: E402

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

# Experiments with no O2 column that burned in normal cabin air (~21% O2).
O2_DEFAULT = {"PSI-26": 21.0, "PSI-100": 21.0}
# NASA notes say pressure varied but wasn't recorded: don't assume 1 atm.
NO_PRESSURE_ASSUMPTION = {"PSI-20"}

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
    m = re.search(r"-?\d*\.?\d+", str(x))
    return float(m.group()) if m else None


def nums(x):
    """All values in a cell. NASA summary rows list several, e.g. '21; 26.5; 40'.
    Ranges like '1.5 - 5' are NOT split (only ';' and 'or')."""
    if x is None or not str(x).strip():
        return [None]
    parts = re.split(r";|\bor\b", str(x))
    vals = [num(p) for p in parts if num(p) is not None]
    return vals or [None]


def to_pct(v, header):
    if v is None:
        return None
    return v * 100 if v <= 1.0 and "%" not in header and "percent" not in norm(header) else v


def to_atm(v, header, cell=""):
    if v is None or v <= 0:          # 0 = not recorded
        return None
    h = norm(header) + " " + str(cell).lower()
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
                                                   r"oxygen mole fraction", r"^oxygen$", r"o2"],
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
        o2_cell = rec.get(cols["o2"]) if cols["o2"] else None
        p_cell = rec.get(cols["p"]) if cols["p"] else None
        o2_list = nums(o2_cell)
        p_list = nums(p_cell)
        multi = len(o2_list) > 1 or len(p_list) > 1
        for o2_raw in o2_list:
            for p_raw in p_list:
                notes = []
                o2 = to_pct(o2_raw, cols["o2"]) if cols["o2"] else None
                if o2 is not None and o2 > 100 and o2 / 100 <= 100:
                    o2 /= 100                      # NASA typo, e.g. "3400%" for 34.00%
                    notes.append("O2 typo corrected")
                if o2 is not None and not (0 < o2 <= 100):
                    o2 = None
                if o2 is None and not cols["o2"] and inv["id"] in O2_DEFAULT:
                    o2 = O2_DEFAULT[inv["id"]]
                    notes.append("O2 assumed 21% (cabin air)")
                p = to_atm(p_raw, cols["p"] or "", p_cell or "") if cols["p"] else None
                if p is not None and not (0 < p < 10):
                    p = None
                if p is None and not cols["p"] and inv["id"] not in NO_PRESSURE_ASSUMPTION:
                    # BASS, Saffire etc. ran in normal spacecraft cabin air (~1 atm).
                    p = 1.0
                    notes.append("pressure assumed 1 atm (cabin air)")
                if inverse and o2 is not None:
                    # Inverse flames: oxygen flows OUT of the burner, so this is burner O2, not cabin air.
                    notes.append("burner O2 (inverse flame)")
                if multi:
                    notes.append("expanded from a NASA summary row")
                out.append({
                    "psi_id": inv["id"], "acronym": inv["acronym"], "table": table_file, "row": i,
                    "o2_pct": round(o2, 2) if o2 is not None else "",
                    "pressure_atm": round(p, 3) if p is not None else "",
                    "airflow_cms": flow if (flow := num(rec.get(cols["flow"])) if cols["flow"] else None) is not None and flow >= 0 else "",
                    "fuel": (rec.get(cols["fuel"]) or "").strip() if cols["fuel"] else "",
                    "outcome": (rec.get(cols["outcome"]) or "").strip() if cols["outcome"] else "",
                    "o2_note": "; ".join(notes),
                })
    return out, cols


# Columns that identify a run rather than describe its conditions.
NOT_A_VARIABLE = re.compile(
    r"test|#|date|gmt|time|^day|year|month|number|camera|note|comment|identifier|"
    r"^cir|session|^pi$|frames|gain|^flex|end$|color|ignited|hot ignition|self.?ext|"
    r"after|final|burn ?time|peak|duration|burning rate|burnrate|length|"
    r"extinction diameter|tad|zst|tfp|mhc|loss|rt/r0|spread|co2 % by vol|co \(ppm\)|"
    r"description|cool flame\?", re.I)


def describe_variables(inv):
    """Which conditions changed between runs, and which were held fixed.
    Values are pooled across all of an investigation's tables first."""
    values = {}
    for t in inv["tables"]:
        rows = list(csv.reader((DATA / "tables" / t["file"]).read_text(errors="replace").splitlines()))
        if len(rows) < 2:
            continue
        headers = [re.sub(r"\s+", " ", h.replace("\ufeff", "")).strip() for h in rows[0]]
        body = [r for r in rows[1:] if any(c.strip() for c in r)]
        for j, h in enumerate(headers):
            if not h or NOT_A_VARIABLE.search(h):
                continue
            for r in body:
                if j < len(r) and r[j].strip():
                    values.setdefault(h, {})[r[j].strip()] = True
    varied, fixed = [], []
    for h, vals in values.items():
        vals = list(vals)
        listed = len(vals) == 1 and re.search(r";| - |\bor\b", vals[0])
        if len(vals) > 1:
            varied.append(f"{h} ({len(vals)} values)")
        elif listed:
            varied.append(f"{h} ({vals[0][:40]})")
        else:
            fixed.append(f"{h}: {vals[0][:40]}")
    return varied[:8], fixed[:6]


def summarize(rows):
    def rng(key):
        v = [r[key] for r in rows if isinstance(r[key], (int, float))]
        return [round(min(v), 2), round(max(v), 2)] if v else None
    fuels = Counter(r["fuel"] for r in rows
                    if r["fuel"] and len(r["fuel"]) <= 40 and "data" not in r["fuel"].lower())
    return {
        "o2_range": rng("o2_pct"),
        "pressure_range": rng("pressure_atm"),
        "airflow_range": rng("airflow_cms"),
        "samples": [f for f, _ in fuels.most_common(6)],
    }


def main():
    invs = json.loads((DATA / "investigations.json").read_text())
    all_rows, catalog = [], []
    print(f"{'ID':8} {'Acronym':22} rows  O2 col / pressure col / flow col")
    for inv in invs:
        tag = TAGS.get(inv["acronym"], DEFAULT_TAG)
        n_rows = 0
        inv_rows = []
        for t in inv["tables"]:
            rows, cols = clean_table(inv, t["file"])
            all_rows += rows
            inv_rows += rows
            n_rows += len(rows)
            print(f"{inv['id']:8} {inv['acronym'][:22]:22} {len(rows):4}  "
                  f"{cols.get('o2')} / {cols.get('p')} / {cols.get('flow')}")
        varied, fixed = describe_variables(inv)
        catalog.append({**inv, **tag, **PROFILES.get(inv["id"], {}), **summarize(inv_rows),
                        "varied": varied, "fixed": fixed,
                        "test_rows": len({(r["table"], r["row"]) for r in inv_rows})})

    with open(DATA / "tests.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_rows)
    (DATA / "catalog.json").write_text(json.dumps(catalog, indent=2))
    print(f"\n{len(all_rows)} test rows -> data/tests.csv")
    print(f"{len(catalog)} investigations -> data/catalog.json")


if __name__ == "__main__":
    main()
