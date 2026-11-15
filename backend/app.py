"""
FlameWatch backend.

Run from the project root:   uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
Then open http://localhost:8000

Endpoints
  POST /api/reading        ESP32 sends live sensor readings here (JSON). Shared by everyone.
  GET  /api/state          habitat conditions + risk for the habitat in the query
  GET  /api/rank           experiments ranked for that habitat
  GET  /api/compare        side-by-side profiles (ids=PSI-1,PSI-2,...)
  GET  /api/export         CSV of test runs (scope=near or scope=ids)
  GET  /api/state?sim_smoke=..&sim_temp=..  simulated fire for the demo button (this browser only)
  GET  /api/points         every NASA test point (O2 vs pressure) for the gaps chart
  POST /api/ask            AI answer grounded in NASA data (needs ANTHROPIC_API_KEY)
  POST /api/scenario       legacy: validates a scenario key and returns that habitat

Habitat is per request, not stored on the server. Pass ?scenario=<key> (default
moonbase), or ?o2_pct=..&pressure_psi=.., plus &sensor=true to use live sensor
readings when the box is connected. Unknown scenario keys return 400.
"""
import csv
import io
import json
import os
import re
import threading
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

app = FastAPI(title="FlameWatch")

# Lets the GitHub Pages site (a different domain) call this API.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------- data ----------

def load():
    catalog = json.loads((DATA / "catalog.json").read_text())
    tests = []
    with open(DATA / "tests.csv") as f:
        for r in csv.DictReader(f):
            for k in ("o2_pct", "pressure_atm", "airflow_cms"):
                r[k] = float(r[k]) if r[k] not in ("", None) else None
            tests.append(r)
    return catalog, tests

CATALOG, TESTS = load()
MAP = json.loads((DATA / "map.json").read_text()) if (DATA / "map.json").exists() else {"families": [], "links": []}
BY_ID = {c["id"]: c for c in CATALOG}

# ---------- habitat state ----------

PSI_PER_ATM = 14.696
SCENARIOS = {
    "iss":      {"label": "ISS / Earth-like cabin",     "o2_pct": 21.0,  "pressure_psi": 14.7},
    "moonbase": {"label": "Moon base (NASA Exploration Atmosphere)", "o2_pct": 34.0, "pressure_psi": 8.2},
    "moon_alt": {"label": "Moon base (challenge brief estimate)", "o2_pct": 30.0, "pressure_psi": 10.2},
    "rover":    {"label": "Pressurized rover",          "o2_pct": 34.0,  "pressure_psi": 8.2},
    "suit":     {"label": "Spacesuit",                  "o2_pct": 100.0, "pressure_psi": 4.3},
}

DEFAULT_SCENARIO = "moonbase"

# Live sensor readings are shared (there's one physical box). The habitat a visitor
# is looking at is NOT shared: each request says which habitat it means.
LIVE = {"o2_pct": None, "pressure_psi": None, "smoke": None, "temp_c": None,
        "dust": None, "flame": None, "updated": 0.0,
        "crew": None, "hatch_cm": None, "suppress_until": 0.0}
LIVE_TIMEOUT_S = 10

# Sensor-box extras (PIR, ultrasonic hatch sensor, suppression switch, vent servo)
SUPPRESS_SECONDS = 15    # how long one press of the box's switch "floods" the module
HATCH_CLOSED_CM = 8      # ultrasonic: anything closer than this = hatch closed

# Vent trigger = rate-of-rise heat detection (like many real fire detectors):
# the vent closes when temperature climbs above the room's learned normal.
# Oxygen makes it more sensitive: +4 °C above normal at 21% O2, down to +2 °C at 40%.
# Scaled so a warm hand on the probe can trigger it in the demo.
RISE_AT_21 = 4.0
RISE_AT_40 = 2.0
RISE_HYSTERESIS = 1.0    # reopen only once it has cooled 1 °C below the trigger
HEAT_ABSOLUTE_C = 45.0   # always counts as heat, whatever the baseline
CRITICAL_RISE = 4.0      # a rise this big above normal = Warning (alarm sounds)
SMOKE_VENT = 60          # smoke reading that counts as fire evidence (closes the vent)
HEAT = {"baseline": None, "detected": False}


def rise_trigger(o2):
    frac = max(0.0, min(1.0, (o2 - 21) / 19))
    return RISE_AT_21 + (RISE_AT_40 - RISE_AT_21) * frac


def update_heat(temp, o2):
    """Learn the room's normal temperature and decide if a heat rise is under way."""
    if temp is None:
        return
    base = HEAT["baseline"]
    if base is None:
        HEAT["baseline"] = temp
        return
    rise = temp - base
    # Follow the room quickly while things are calm; nearly freeze while heating,
    # so holding the probe doesn't teach the box that "hot" is normal.
    HEAT["baseline"] += (temp - base) * (1 / 30 if rise < 1.5 else 1 / 1200)
    trigger = rise_trigger(o2 or 21)
    if HEAT["detected"]:
        HEAT["detected"] = rise >= trigger - RISE_HYSTERESIS or temp >= HEAT_ABSOLUTE_C
    else:
        HEAT["detected"] = rise >= trigger or temp >= HEAT_ABSOLUTE_C


def live_fresh():
    return time.time() - LIVE["updated"] < LIVE_TIMEOUT_S


def habitat(scenario=None, o2_pct=None, pressure_psi=None, sensor=False):
    """Resolve the conditions a request is asking about.
    scenario: a preset key (default: moonbase). o2_pct/pressure_psi override it.
    sensor: use the live sensor box readings (if fresh) on top."""
    key = scenario or DEFAULT_SCENARIO
    if key not in SCENARIOS:
        raise HTTPException(400, f"Unknown scenario '{key}'. Use one of: {', '.join(SCENARIOS)}.")
    base = SCENARIOS[key]
    h = {"scenario": key, "label": base["label"], "source": "preset",
         "o2_pct": base["o2_pct"], "pressure_psi": base["pressure_psi"],
         "smoke": 0.0, "temp_c": 22.0, "dust": None, "flame": False}
    if o2_pct is not None:
        if not 0 < o2_pct <= 100:
            raise HTTPException(400, "o2_pct must be between 0 and 100.")
        h.update(o2_pct=o2_pct, source="custom", label="Custom conditions")
    if pressure_psi is not None:
        if not 0 < pressure_psi <= 30:
            raise HTTPException(400, "pressure_psi must be between 0 and 30.")
        h.update(pressure_psi=pressure_psi, source="custom", label="Custom conditions")
    if sensor and live_fresh():
        h.update({k: LIVE[k] for k in ("o2_pct", "pressure_psi", "smoke", "temp_c", "dust", "flame")
                  if LIVE[k] is not None})
        h.update(source="sensor", label="Sensor box (live)")
        if LIVE["temp_c"] is not None and HEAT["baseline"] is not None:
            h["heat_rise"] = LIVE["temp_c"] - HEAT["baseline"]   # unrounded: same value the vent uses
    return h


class Reading(BaseModel):
    o2_pct: float | None = None        # from the knob (simulated)
    pressure_psi: float | None = None  # BMP280, or omit
    smoke: float | None = None         # MQ sensor, 0-100 scaled on the ESP32
    temp_c: float | None = None
    dust: float | None = None
    flame: bool | None = None
    crew: bool | None = None           # PIR motion sensor: crew in the module
    hatch_cm: float | None = None      # ultrasonic distance to the hatch
    suppress: bool | None = None       # switch pressed since the last reading


SEA_LEVEL_PPO2_PSI = 0.21 * 14.696   # ≈ 3.1 psi

RISK_FORMULA = {
    "oxygen": "60 × (O₂% − 21) ÷ 19, from 0 at 21% up to a maximum of 60 at 40% or more",
    "smoke": "Smoke reading (0–100) × 0.25, maximum 25",
    "heat": "0 at 30 °C or below, rising to 15 at 60 °C: 15 × (°C − 30) ÷ 30",
    "flame": "25 if the flame sensor detects a flame, otherwise 0",
    "levels": ("Nominal under 30 · Caution 30–59 · Warning 60 or more. Overrides: any flame means "
               "Warning; smoke of 85 or more means Warning; smoke of 60 or more means at least Caution; "
               "with the sensor box, a temperature rise of 4 °C or more above the room's normal means Warning"),
    "why_concentration": ("The oxygen score uses oxygen concentration (%), not partial pressure. "
                          "A Moon base at 34% O₂ and 8.2 psi has a lower oxygen partial pressure "
                          "than sea level, yet NASA expects materials to burn more easily there: "
                          "flammability tracks the oxygen fraction more closely than its partial pressure."),
}


def risk(state):
    """Simple, explainable fire-risk score (0-100). Not a validated model: it
    combines how flammable the atmosphere is with what the sensors detect."""
    o2 = state["o2_pct"]
    atmo = max(0.0, min(60.0, (o2 - 21) / 19 * 60))
    smoke = min(25.0, (state.get("smoke") or 0) / 100 * 25)
    heat = max(0.0, min(15.0, ((state.get("temp_c") or 22) - 30) / 30 * 15))
    flame = 25.0 if state.get("flame") else 0.0
    score = min(100.0, atmo + smoke + heat + flame)
    smoke_reading = state.get("smoke") or 0
    heat_rise = state.get("heat_rise") or 0      # sensor box only: °C above the room's normal
    if score >= 60 or state.get("flame") or smoke_reading >= 85 or heat_rise >= CRITICAL_RISE:
        level = "red"
    elif score >= 30 or smoke_reading >= 60:
        level = "yellow"
    else:
        level = "green"
    ppo2 = o2 / 100 * state["pressure_psi"]
    explain = (f"Oxygen adds {round(atmo)} because the air is {o2:.0f}% oxygen "
               f"(Earth: 21%). Oxygen partial pressure here is {ppo2:.1f} psi vs "
               f"{SEA_LEVEL_PPO2_PSI:.1f} psi at sea level.")
    return {"score": round(score), "level": level, "explain": explain,
            "ppo2_psi": round(ppo2, 2), "formula": RISK_FORMULA,
            "parts": {"atmosphere": round(atmo), "smoke": round(smoke),
                      "heat": round(heat), "flame": round(flame)}}


@app.post("/api/reading")
def post_reading(r: Reading):
    data = r.model_dump()
    suppress = data.pop("suppress")
    LIVE.update({k: v for k, v in data.items() if v is not None})
    LIVE["updated"] = time.time()
    if suppress:
        LIVE["suppress_until"] = time.time() + SUPPRESS_SECONDS
    update_heat(data.get("temp_c"), LIVE["o2_pct"])
    # Small reply so the ESP32 can set its LEDs, buzzer and vent servo from it.
    box = box_status()
    return {"level": box["level"], "mode": box["mode"], "vent": box["vent"],
            "alarm": box["alarm"]}


def box_status():
    """Module status from the sensor box, judged on the box's own live readings.
    The vent closes when heat or smoke is detected (evidence of a fire) or while suppressing,
    not for high oxygen alone: in microgravity, ventilation is what clears the crew's
    exhaled CO2, so shutting it with no fire would hurt them. Once a fire starts,
    forced airflow is what feeds it (no buoyancy), so then it closes."""
    level = risk(habitat(sensor=True))["level"]
    suppressing = time.time() < LIVE["suppress_until"]
    hatch = LIVE["hatch_cm"]
    temp, base = LIVE["temp_c"], HEAT["baseline"]
    rise = None if temp is None or base is None else round(temp - base, 1)
    heat = HEAT["detected"]
    smoky = (LIVE["smoke"] or 0) >= SMOKE_VENT
    return {"level": level, "mode": "suppressing" if suppressing else "normal",
            "vent": "closed" if suppressing or heat or smoky else "open",
            "smoke_detected": smoky,
            "alarm": level == "red" and not suppressing,
            "heat_detected": heat, "temp_rise": rise,
            "rise_trigger": round(rise_trigger(LIVE["o2_pct"] or 21), 1),
            "baseline_c": None if base is None else round(base, 1),
            "crew": LIVE["crew"], "hatch_cm": hatch,
            "hatch_closed": None if hatch is None else hatch < HATCH_CLOSED_CM}


def state_payload(h):
    return {**h, "live": live_fresh(), "risk": risk(h), "scenarios": SCENARIOS,
            "default_scenario": DEFAULT_SCENARIO,
            "box": box_status() if live_fresh() else None}


def sim_payload(h, smoke, temp_c, flame, crew, hatch_closed, suppressing):
    """A simulated fire for the demo button. Per request and never stored, so it only
    affects the browser that asked. Uses the same risk rules and vent logic as the real box."""
    base_c = 22.0
    h.update(smoke=max(0.0, min(100.0, smoke)), temp_c=temp_c, flame=flame,
             heat_rise=temp_c - base_c, source="simulation", label="Simulated fire")
    r = risk(h)
    trigger = rise_trigger(h["o2_pct"])
    heat = temp_c - base_c >= trigger or temp_c >= HEAT_ABSOLUTE_C
    smoky = h["smoke"] >= SMOKE_VENT
    box = {"level": r["level"], "mode": "suppressing" if suppressing else "normal",
           "vent": "closed" if suppressing or heat or smoky else "open",
           "smoke_detected": smoky, "alarm": r["level"] == "red" and not suppressing,
           "heat_detected": heat, "temp_rise": round(temp_c - base_c, 1),
           "rise_trigger": round(trigger, 1), "baseline_c": base_c,
           "crew": crew, "hatch_cm": 3 if hatch_closed else 40, "hatch_closed": hatch_closed}
    return {**h, "live": live_fresh(), "risk": r, "scenarios": SCENARIOS,
            "default_scenario": DEFAULT_SCENARIO, "box": box, "simulated": True}


@app.get("/api/state")
def get_state(scenario: str | None = None, o2_pct: float | None = None,
              pressure_psi: float | None = None, sensor: bool = False,
              sim_smoke: float | None = None, sim_temp: float | None = None,
              sim_flame: bool = False, sim_crew: bool = False,
              sim_hatch: bool = False, sim_suppress: bool = False):
    if sim_smoke is not None and sim_temp is not None:
        if not -50 <= sim_temp <= 200:
            raise HTTPException(400, "sim_temp must be between -50 and 200.")
        return sim_payload(habitat(scenario, o2_pct, pressure_psi, False), sim_smoke, sim_temp,
                           sim_flame, sim_crew, sim_hatch, sim_suppress)
    return state_payload(habitat(scenario, o2_pct, pressure_psi, sensor))


class Scenario(BaseModel):
    key: str


@app.post("/api/scenario")
def check_scenario(s: Scenario):
    """Kept for older clients. Stateless: validates the key and returns that habitat."""
    return state_payload(habitat(s.key))

# ---------- ranking ----------

# A NASA test run counts as "near" the habitat when BOTH hold:
NEAR_RULE = {"o2_points": 4.0,       # oxygen within ±4 percentage points
             "pressure_frac": 0.30}  # pressure within ±30% of the habitat's
NEAR_RULE_TEXT = (f"within ±{NEAR_RULE['o2_points']:g} points of oxygen "
                  f"and ±{NEAR_RULE['pressure_frac']:.0%} of pressure")
NEAR_RULE_NOTE = ("Experiments that only publish summary ranges (FLEX-2, ACME BRE) "
                  "can't be matched run by run, so they're never counted as near.")


def _usable(test):
    # Inverse flames: the O2 value is burner gas, not the cabin atmosphere.
    return test["o2_pct"] is not None and "burner" not in (test.get("o2_note") or "")


def is_near(test, o2, p_atm):
    if not _usable(test) or test["pressure_atm"] is None:
        return False
    # Summary rows (e.g. FLEX-2) list several conditions per row, so we can't tell
    # which combination was actually burned. Never count them as near.
    if "summary row" in (test.get("o2_note") or ""):
        return False
    return (abs(test["o2_pct"] - o2) <= NEAR_RULE["o2_points"]
            and abs(test["pressure_atm"] - p_atm) <= NEAR_RULE["pressure_frac"] * p_atm)


def closeness(test, o2, p_atm):
    """0..1 similarity used for ranking. Exactly 0.5 at the edge of the near rule,
    so anything near scores >= 0.5. None if the run has no usable cabin O2."""
    if not _usable(test):
        return None
    d_o2 = abs(test["o2_pct"] - o2) / (2 * NEAR_RULE["o2_points"])
    if test["pressure_atm"] is None:
        d_p = 0.5   # unknown pressure: partial credit, never "near"
    else:
        d_p = abs(test["pressure_atm"] - p_atm) / (2 * NEAR_RULE["pressure_frac"] * p_atm)
    return max(0.0, 1 - max(d_o2, d_p))


@app.get("/api/rank")
def rank(area: str = "all", limit: int = 30, scenario: str | None = None,
         o2_pct: float | None = None, pressure_psi: float | None = None, sensor: bool = False):
    h = habitat(scenario, o2_pct, pressure_psi, sensor)
    o2, p_atm = h["o2_pct"], h["pressure_psi"] / PSI_PER_ATM
    results = []
    for inv in CATALOG:
        tests = [t for t in TESTS if t["psi_id"] == inv["id"]]
        scored = [(closeness(t, o2, p_atm), t) for t in tests]
        scored = [x for x in scored if x[0] is not None]
        best = max((s for s, _ in scored), default=0.0)
        # Count original NASA rows (summary rows can expand into several points).
        n_tests = len({(t["table"], t["row"]) for t in tests})
        near = len({(t["table"], t["row"]) for _, t in scored if is_near(t, o2, p_atm)})
        o2s = [t["o2_pct"] for t in tests if t["o2_pct"] is not None]
        # Score = condition match (50) + crew relevance (30) + area match (20)
        area_match = area == "all" or area in inv.get("areas", [])
        score = 50 * best + 10 * inv.get("crew_relevance", 1) + (20 if area_match else 0)
        if not area_match:
            score *= 0.5
        results.append({
            "id": inv["id"], "acronym": inv["acronym"], "title": inv["title"],
            "doi": inv.get("doi"), "url": inv["url"], "areas": inv.get("areas", []),
            "fuel_kind": inv.get("fuel_kind"), "crew_relevance": inv.get("crew_relevance", 1),
            "shape": inv.get("shape", "model"), "photo": bool(inv.get("photo_file")),
            "family": inv.get("family", "other"),
            "score": round(score, 1),
            "match": round(best, 2), "tests_total": n_tests, "tests_near": near,
            "o2_range": [min(o2s), max(o2s)] if o2s else None,
            "objectives": (inv.get("objectives") or "")[:400],
            "why": explain(inv, best, near, area_match),
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return {"conditions": {"o2_pct": o2, "pressure_atm": round(p_atm, 3)},
            "near_rule": NEAR_RULE_TEXT, "near_note": NEAR_RULE_NOTE, "results": results[:limit]}


def explain(inv, best, near, area_match):
    bits = []
    if near:
        bits.append(f"{near} test runs {NEAR_RULE_TEXT} of this habitat")
    elif best > 0.25:
        bits.append("some test runs in a similar oxygen/pressure range")
    else:
        bits.append("no test runs near these conditions")
    if inv.get("crew_relevance", 1) >= 3:
        if "emulator" in (inv.get("fuel_kind") or ""):
            bits.append("gas burner built to imitate burning cabin materials")
        elif inv.get("fuel_kind") == "smoke":
            bits.append("measured smoke from cabin materials")
        else:
            bits.append(f"burned {inv.get('fuel_kind')} materials like those in a crew cabin")
    if not area_match:
        bits.append("outside the selected safety area")
    return "; ".join(bits)


@app.get("/api/points")
def points():
    return [{"id": t["psi_id"], "acronym": t["acronym"], "o2": t["o2_pct"],
             "p": t["pressure_atm"], "note": t["o2_note"],
             "area": (BY_ID.get(t["psi_id"], {}).get("areas") or ["prevention"])[0]}
            for t in TESTS if t["o2_pct"] is not None and t["pressure_atm"] is not None]

# ---------- compare + export ----------

COMPARE_FIELDS = ["id", "acronym", "title", "doi", "url", "project_type", "areas", "hardware",
                  "shape", "family",
                  "fuel", "samples", "measured", "agents", "o2_range", "pressure_range",
                  "airflow_range", "airflow_note",
                  "varied", "fixed", "test_rows", "objectives"]


@app.get("/api/compare")
def compare(ids: str, scenario: str | None = None, o2_pct: float | None = None,
            pressure_psi: float | None = None, sensor: bool = False):
    """Side-by-side profiles for up to 3 investigations (comma-separated PSI IDs)."""
    h = habitat(scenario, o2_pct, pressure_psi, sensor)
    o2, p_atm = h["o2_pct"], h["pressure_psi"] / PSI_PER_ATM
    out = []
    for pid in [i.strip() for i in ids.split(",") if i.strip()][:3]:
        inv = BY_ID.get(pid)
        if not inv:
            continue
        tests = [t for t in TESTS if t["psi_id"] == pid]
        near = {(t["table"], t["row"]) for t in tests if is_near(t, o2, p_atm)}
        prof = {k: inv.get(k) for k in COMPARE_FIELDS}
        prof["hardware"] = prof["hardware"] if isinstance(prof["hardware"], str) else ""
        prof["objectives"] = (prof["objectives"] or "")[:500]
        prof["tests_near"] = len(near)
        prof["photo"] = bool(inv.get("photo_file"))
        out.append(prof)
    return {"conditions": {"o2_pct": o2, "pressure_atm": round(p_atm, 3)}, "investigations": out}


EXPORT_COLUMNS = ["psi_id", "acronym", "doi", "o2_pct", "pressure_atm", "airflow_cms",
                  "fuel", "outcome", "outcome_measure", "near_habitat", "match_to_habitat",
                  "note", "source_table", "source_row"]


@app.get("/api/export")
def export(scope: str = "near", ids: str = "", scenario: str | None = None,
           o2_pct: float | None = None, pressure_psi: float | None = None, sensor: bool = False):
    """Download NASA test runs as CSV.
    scope=near: runs close to the current habitat (all experiments)
    scope=ids:  every run from the listed experiments (comma-separated PSI IDs)"""
    h = habitat(scenario, o2_pct, pressure_psi, sensor)
    o2, p_atm = h["o2_pct"], h["pressure_psi"] / PSI_PER_ATM
    wanted = {i.strip() for i in ids.split(",") if i.strip()}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(EXPORT_COLUMNS)
    for t in TESTS:
        match = closeness(t, o2, p_atm)
        if scope == "near" and not is_near(t, o2, p_atm):
            continue
        if scope == "ids" and t["psi_id"] not in wanted:
            continue
        w.writerow([t["psi_id"], t["acronym"], BY_ID.get(t["psi_id"], {}).get("doi", ""),
                    t["o2_pct"], t["pressure_atm"], t["airflow_cms"], t["fuel"], t["outcome"],
                    t.get("outcome_col", ""), "yes" if is_near(t, o2, p_atm) else "no",
                    "" if match is None else round(match, 2), t["o2_note"], t["table"], t["row"]])
    name = (f"flamewatch_runs_near_{round(o2)}pct_{h['pressure_psi']:.1f}psi.csv" if scope == "near"
            else f"flamewatch_runs_{'_'.join(sorted(wanted)) or 'none'}.csv")
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---------- connection map + photos ----------

@app.get("/api/map")
def experiment_map(scenario: str | None = None, o2_pct: float | None = None,
                   pressure_psi: float | None = None, sensor: bool = False):
    """Experiments grouped by shared hardware, with the links between them."""
    h = habitat(scenario, o2_pct, pressure_psi, sensor)
    o2, p_atm = h["o2_pct"], h["pressure_psi"] / PSI_PER_ATM
    nodes = []
    for inv in CATALOG:
        tests = [t for t in TESTS if t["psi_id"] == inv["id"]]
        near = {(t["table"], t["row"]) for t in tests if is_near(t, o2, p_atm)}
        nodes.append({"id": inv["id"], "acronym": inv.get("acronym") or "", "title": inv["title"],
                      "url": inv["url"], "family": inv.get("family", "other"),
                      "shape": inv.get("shape", "model"), "photo": bool(inv.get("photo_file")),
                      "badge": inv.get("badge", ""), "areas": inv.get("areas", []),
                      "project_type": inv.get("project_type", ""),
                      "tests_total": inv.get("test_rows", 0), "tests_near": len(near)})
    return {"families": MAP["families"], "links": MAP["links"], "nodes": nodes,
            "near_rule": NEAR_RULE_TEXT}


PHOTO_DIR = DATA / "photos"
PSI_API = "https://psi.nasa.gov/geode-py/ws"


@app.get("/api/photo/{pid}")
def photo(pid: str):
    """NASA's representative image for an investigation. Downloaded from PSI the
    first time, then served from data/photos/ (so it works offline afterwards)."""
    inv = BY_ID.get(pid)
    if not inv or not inv.get("photo_file"):
        raise HTTPException(404, "No NASA image for this investigation.")
    path = PHOTO_DIR / f"{pid}.jpg"
    if not path.exists():
        import requests
        PHOTO_DIR.mkdir(parents=True, exist_ok=True)
        for version in (1, 2, 3, 4, 5):
            try:
                r = requests.get(f"{PSI_API}/studies/{pid}/download", timeout=15,
                                 params={"file": inv["photo_file"], "version": version, "redirect": "false"})
                url = r.text.strip().strip('"') if r.ok else ""
                if not url.startswith("http"):
                    continue
                img = requests.get(url, timeout=30)
                if img.ok and img.headers.get("content-type", "").startswith("image"):
                    path.write_bytes(img.content)
                    break
            except requests.RequestException:
                continue
        if not path.exists():
            raise HTTPException(404, "Couldn't download the NASA image right now.")
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


# ---------- AI ----------

class Question(BaseModel):
    question: str
    scenario: str | None = None
    o2_pct: float | None = None
    pressure_psi: float | None = None
    sensor: bool = False


def trim(text, limit):
    """Shorten at a sentence boundary; never leave a dangling half-sentence."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[:end + 1] if end > limit * 0.4 else cut.rsplit(" ", 1)[0] + "…"


def fmt_range(r, unit):
    return "not recorded" if not r else (f"{r[0]:g}{unit}" if r[0] == r[1] else f"{r[0]:g}–{r[1]:g}{unit}")


# Facts from outside the PSI database, so the AI doesn't contradict them.
OUTSIDE_PSI = """Results NOT in the PSI database (published elsewhere by NASA):
- Saffire-V (Cygnus, 2020): burned cotton jersey fabric at 26.2% O2 and 70.7 kPa (about 10.3 psi).
- Saffire-VI (Cygnus, final flight 2023-24): burned SIBAL fabric at 31.0% O2 and 54.1 kPa (about 7.8 psi),
  and 1 cm and 0.5 cm thick PMMA at 30.3% and 28.8% O2 at about 55 kPa (about 8.0 psi), all at 20 cm/s airflow.
  Source: NASA, "Preliminary Results from the Saffire VI Experiment", ICES 2024.
- LUCI (Lunar Combustion Investigation, Blue Origin New Shepard, flew Feb 2025): the capsule spun to simulate
  lunar gravity. It burned SIBAL cotton-fiberglass fabric (5 x 30 cm) and a 4 mm acrylic (PMMA) rod in air at
  normal pressure, and compared them with the same burns on Earth (fitted spread rates, NASA NTRS 20250010653):
    SIBAL flame base: Moon 0.9 mm/s vs Earth 1.5 mm/s (ratio 0.6)
    SIBAL flame tip:  Moon 1.1 mm/s vs Earth 2.8 mm/s (ratio 0.39)
    PMMA flame tip:   Moon 1.5 mm/s vs Earth 4.0 mm/s (ratio 0.38)
  So in normal air, flames spread SLOWER in lunar gravity than on Earth. This does not contradict the oxygen-limit
  results below: a flame can spread more slowly yet still survive at lower oxygen. Not in PSI yet.
- FM2 (Flammability of Materials on the Moon): the first fire experiment on the Moon, planned for late 2026.
- Olson & Ferkul 2012, "Evaluating Material Flammability in Microgravity and Martian Gravity Compared to the
  NASA Standard Normal Gravity Test" (NASA NTRS 20130010991, Table I). Lowest oxygen (molar %) at which each
  material's flame survived, by gravity (ULOI; low-g values use flame survival during ~5 s drop-tower tests,
  lunar and Martian gravity made with a centrifuge in the drop tower, so criteria differ from Earth's NASA-STD-6001 test):
    Mylar G film (10.2 psia):   Earth 21.2 | Mars 18.0 | Moon 15.6 | Orbit (0g, 30 cm/s flow) 17.0
    Ultem 1000 (10.2 psia):     Earth 23.5 | Mars 22.0 | Moon 21.0 | Orbit 24.0
    Nomex HT90-40 (14.7 psia):  Earth 23.5 | Mars 19.9 | Moon 21.0 | Orbit 23.0
  The authors conclude that normal-gravity flammability screening "may not be conservative": all three materials
  burned at lower oxygen in lunar gravity than on Earth, and Mylar's lunar limit was the lowest of all.
- Urban et al. 2025, "Solid Fuel Ignition Testing for Lunar Applications" (ICES-2025-392, NASA NTRS 20250002114,
  Table 2 "Flammability Compensation Factors"). A conservative (95% confidence), model-based estimate of how many
  oxygen percentage points a material's Earth (NASA Test 1) flammability limit should be adjusted for lunar gravity,
  extrapolating from the ~35 cm/s buoyant flow on Earth to near-zero flow:
    PMMA 1.9 | polycarbonate 2.3 | Nomex Velcro 0.32 | P 213 1.4 | Beefy-T cotton shirt, flaming 0.82 | smoldering 1.8
  Use it as a safety margin: a material that only just passes Earth's test may not pass in lunar gravity."""

# Words a question might use -> text to look for in an investigation's profile.
KEYWORDS = {
    "helium": ["helium"], "co2": ["co₂", "co2"], "carbon dioxide": ["co₂", "co2"],
    "nitrogen": ["nitrogen"], "suppress": ["suppress", "extinguish"], "extinguish": ["suppress", "extinguish"],
    "droplet": ["droplet"], "liquid": ["droplet"], "pmma": ["pmma"], "acrylic": ["pmma"], "plastic": ["pmma", "plastic"],
    "fabric": ["fabric", "sibal", "nomex"], "cotton": ["cotton", "sibal"], "sibal": ["sibal"], "nomex": ["nomex"],
    "silicone": ["silicone"], "kapton": ["kapton"], "teflon": ["teflon"], "smoke": ["smoke"],
    "soot": ["soot"], "dust": ["dust"], "detect": ["smoke", "detector"], "cool flame": ["cool"],
    "methane": ["methane"], "ethylene": ["ethylene"], "propane": ["propane"], "heptane": ["heptane"],
    "methanol": ["methanol"], "electric": ["electric"], "candle": ["candle", "wax"], "wax": ["wax"],
    "spread": ["spread"], "radiat": ["radiat"], "pressure": [], "lunar": ["partial gravity"],
}


def profile_text(inv):
    return " ".join(str(inv.get(k) or "") for k in
                    ("acronym", "title", "fuel", "measured", "agents", "samples", "varied")).lower()


def mentioned(question):
    """Investigations the question names (ID, acronym) or matches by keyword,
    strongest match first."""
    q = question.lower()
    scored = []
    for inv in CATALOG:
        acr = (inv.get("acronym") or "").lower()
        names = [inv["id"].lower()] + [a.strip() for a in re.split(r"[/ ]+", acr) if len(a.strip()) >= 3]
        if any(re.search(rf"\b{re.escape(n)}\b", q) for n in names):
            scored.append((100, inv["id"]))
            continue
        text = profile_text(inv)
        hits = sum(1 for k, terms in KEYWORDS.items()
                   if terms and k in q and any(t in text for t in terms))
        if hits:
            scored.append((hits, inv["id"]))
    scored.sort(key=lambda x: -x[0])
    return [pid for _, pid in scored]


def summary_line(inv):
    return (f"- {inv['id']} {inv.get('acronym') or ''}: {trim(inv['title'], 90)}. "
            f"Areas: {', '.join(inv.get('areas') or [])}. Runs: {inv.get('test_rows', 0)}. "
            f"Burned: {trim(inv.get('fuel') or 'n/a', 160)}. "
            f"Measured: {trim(inv.get('measured') or 'n/a', 120)}. "
            + (f"Agents/diluents: {inv['agents']}. " if inv.get("agents") else "")
            + f"O2: {fmt_range(inv.get('o2_range'), '%')}; pressure: {fmt_range(inv.get('pressure_range'), ' atm')}; "
            f"airflow: {fmt_range(inv.get('airflow_range'), ' cm/s')}.")


def detail_block(pid, o2, p_atm):
    inv = BY_ID[pid]
    tests = [t for t in TESTS if t["psi_id"] == pid]
    tests.sort(key=lambda t: closeness(t, o2, p_atm) or -1, reverse=True)
    rows = []
    for t in tests[:10]:
        bits = [f"O2 {t['o2_pct']}%" if t["o2_pct"] is not None else "O2 not recorded",
                f"{t['pressure_atm']} atm" if t["pressure_atm"] is not None else "pressure not recorded"]
        if t["airflow_cms"] is not None:
            bits.append(f"airflow {t['airflow_cms']} cm/s")
        if t["fuel"]:
            bits.append(f"sample: {t['fuel']}")
        if t["outcome"]:
            bits.append(f"{t.get('outcome_col') or 'outcome'} = {t['outcome']}")
        if t["o2_note"]:
            bits.append(f"[{t['o2_note']}]")
        bits.append("NEAR" if is_near(t, o2, p_atm) else "")
        rows.append("  - " + "; ".join(b for b in bits if b))
    return (f"### {pid} {inv.get('acronym') or ''} (DOI {inv.get('doi')})\n"
            f"Changed between runs: {', '.join(inv.get('varied') or []) or 'n/a'}\n"
            f"Objectives: {trim(inv.get('objectives'), 600)}\n"
            f"Hypothesis: {trim(inv.get('hypothesis'), 300)}\n"
            f"Research impacts: {trim(inv.get('impacts'), 400)}\n"
            f"Runs closest to this habitat (NEAR = {NEAR_RULE_TEXT}):\n" + "\n".join(rows))


def build_context(question, h):
    """All 24 investigations in summary, plus details for the best matches to the
    habitat and for anything the question mentions. Independent of UI filters."""
    o2, p_atm = h["o2_pct"], h["pressure_psi"] / PSI_PER_ATM
    top = [r["id"] for r in rank(area="all", limit=5, o2_pct=o2, pressure_psi=h["pressure_psi"])["results"]]
    named = [pid for pid in mentioned(question) if pid not in top][:5]
    summary = "\n".join(summary_line(inv) for inv in CATALOG)
    details = "\n\n".join(detail_block(pid, o2, p_atm) for pid in top + named)
    return (f"ALL {len(CATALOG)} NASA PSI COMBUSTION INVESTIGATIONS (summary):\n{summary}\n\n"
            f"DETAILED DATA (most relevant to this habitat"
            + (f", plus {', '.join(named)} matched from the question" if named else "")
            + f"):\n{details}\n\n{OUTSIDE_PSI}"), top + named


SYSTEM = """You are FlameWatch, a fire-safety assistant for crewed space habitats, used by
aerospace engineers and students. You get a summary of ALL NASA PSI combustion investigations,
detailed test rows for the most relevant ones, and a few NASA results from outside PSI.

How to answer:
- Lead with a direct, useful answer in 1-2 sentences, then 2-4 short bullet points of support.
- Ground claims in the data and cite the PSI ID, e.g. (PSI-69). Use the summary list to find any
  investigation relevant to the question, not only the detailed ones.
- If the user's exact condition isn't covered, first say what the data shows at other conditions
  (with the PSI ID and the conditions), then say what's missing.
- Facts marked "NOT in the PSI database" may be used; say they come from NASA results outside PSI.
- You MAY use well-established combustion and fire-safety science to interpret the data. Mark such
  points with "(general fire science)".
- Never invent numbers. If a value's units are unclear, don't quote it.
- Never mention truncation, missing text, or how the context was assembled.
- Under 180 words. Markdown: **bold** for the key point, "- " for bullets. No headings."""


# ---------- AI usage limits ----------
# Stops one visitor (or a script) from spending the API budget. Counts live in memory,
# so they reset when the server restarts. Set a spend limit in the Anthropic console
# as well: that's the hard cap on what you can be billed.
ASK_PER_MINUTE = int(os.environ.get("ASK_PER_MINUTE", 5))        # per visitor
ASK_PER_DAY = int(os.environ.get("ASK_PER_DAY", 30))             # per visitor
ASK_GLOBAL_PER_DAY = int(os.environ.get("ASK_GLOBAL_PER_DAY", 150))  # whole site
ASK_MAX_CHARS = int(os.environ.get("ASK_MAX_CHARS", 500))
ASK_CACHE_SECONDS = 3600

_ask_lock = threading.Lock()
_ask_by_client: dict[str, deque] = {}
_ask_all: deque = deque()
_answer_cache: dict[tuple, tuple[float, dict]] = {}


def client_id(request: Request) -> str:
    """The visitor's IP. Behind Render's proxy the real address is the last entry the
    proxy appended to X-Forwarded-For (earlier entries can be faked by the client)."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _too_many(message: str, retry_after: int):
    raise HTTPException(429, detail=message, headers={"Retry-After": str(max(1, retry_after))})


def check_ask_limits(who: str):
    now = time.time()
    with _ask_lock:
        mine = _ask_by_client.setdefault(who, deque())
        while mine and now - mine[0] > 86400:
            mine.popleft()
        while _ask_all and now - _ask_all[0] > 86400:
            _ask_all.popleft()
        last_minute = sum(1 for t in mine if now - t < 60)
        if last_minute >= ASK_PER_MINUTE:
            oldest = min(t for t in mine if now - t < 60)
            _too_many(f"That's {ASK_PER_MINUTE} questions in a minute. Try again in a few seconds.",
                      int(60 - (now - oldest)) + 1)
        if len(mine) >= ASK_PER_DAY:
            _too_many(f"You've reached today's limit of {ASK_PER_DAY} questions. Try again tomorrow.",
                      int(86400 - (now - mine[0])) + 1)
        if len(_ask_all) >= ASK_GLOBAL_PER_DAY:
            _too_many("The assistant has reached today's question limit for everyone. Try again tomorrow.",
                      int(86400 - (now - _ask_all[0])) + 1)
        mine.append(now)
        _ask_all.append(now)


def cache_key(q, h):
    question = re.sub(r"\s+", " ", q.question.strip().lower())
    return (question, round(h["o2_pct"], 1), round(h["pressure_psi"], 1),
            h["source"], round(h.get("smoke") or 0, -1), bool(h.get("flame")))


@app.post("/api/ask")
def ask(q: Question, request: Request):
    question = q.question.strip()
    if not question:
        raise HTTPException(400, "Type a question first.")
    if len(question) > ASK_MAX_CHARS:
        raise HTTPException(400, f"Please keep questions under {ASK_MAX_CHARS} characters.")
    h = habitat(q.scenario, q.o2_pct, q.pressure_psi, q.sensor)

    # The same question about the same habitat: reuse the answer, free.
    key_c = cache_key(q, h)
    hit = _answer_cache.get(key_c)
    if hit and time.time() - hit[0] < ASK_CACHE_SECONDS:
        return {**hit[1], "cached": True}

    st = state_payload(h)
    context, used = build_context(question, h)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"answer": "AI is not connected yet (set ANTHROPIC_API_KEY). Most relevant "
                          "experiments right now: " + ", ".join(used[:5]), "sources": used}

    check_ask_limits(client_id(request))   # only real AI calls count
    prompt = (f"Current habitat: {st['label']}, {st['o2_pct']}% O2, "
              f"{st['pressure_psi']} psi, smoke {st['smoke']}/100, temp {st['temp_c']} C, "
              f"fire risk {st['risk']['score']}/100 ({st['risk']['level']}).\n\n"
              f"{context}\n\nQuestion: {question}")
    import anthropic
    client = anthropic.Anthropic(api_key=key, max_retries=1)
    try:
        msg = client.messages.create(
            model=os.environ.get("FLAMEWATCH_MODEL", "claude-sonnet-5-5"),
            max_tokens=2000, system=SYSTEM,
            messages=[{"role": "user", "content": prompt}])
    except anthropic.APIStatusError as e:
        text = str(getattr(e, "message", "")) + str(getattr(e, "body", ""))
        if "usage limit" in text.lower() or "spend_limit" in text.lower():
            raise HTTPException(503, "The assistant has reached its usage limit. The rest of the dashboard still works.")
        if e.status_code == 429:
            raise HTTPException(503, "The assistant is busy right now. Try again in a minute.", headers={"Retry-After": "60"})
        raise HTTPException(502, "The assistant didn't respond. Try again.")
    except anthropic.APIConnectionError:
        raise HTTPException(502, "Couldn't reach the AI service. Check the internet connection and try again.")

    # The reply can contain thinking blocks before the answer; keep only the text.
    answer = "\n".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    answer = re.sub(r"\s*\((?:the )?source text (?:is|was) truncated\)", "", answer, flags=re.I)
    if not answer:
        return {"answer": "The AI didn't return an answer. Try asking again.", "sources": used}
    result = {"answer": answer, "sources": used}
    _answer_cache[key_c] = (time.time(), result)
    if len(_answer_cache) > 500:   # keep memory bounded
        for k in sorted(_answer_cache, key=lambda k: _answer_cache[k][0])[:100]:
            _answer_cache.pop(k, None)
    return result


# ---------- frontend ----------

@app.get("/api/health")
def health():
    return {"ok": True, "investigations": len(CATALOG), "tests": len(TESTS)}


# Must be last: serves the dashboard at "/" (API routes above take priority).
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
