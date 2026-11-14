"""
FlameWatch backend.

Run from the project root:   uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
Then open http://localhost:8000

Endpoints
  POST /api/reading        ESP32 sends live sensor readings here (JSON)
  GET  /api/state          latest habitat conditions + risk (dashboard + ESP32 poll this)
  POST /api/scenario       dashboard sets a preset scenario (when no box is connected)
  GET  /api/rank           experiments ranked for the current conditions
  GET  /api/points         every NASA test point (O2 vs pressure) for the gaps chart
  POST /api/ask            AI answer grounded in NASA data (needs ANTHROPIC_API_KEY)
"""
import csv
import json
import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

STATE = {
    "source": "scenario", "scenario": "iss", **SCENARIOS["iss"],
    "smoke": 0.0, "temp_c": 22.0, "dust": None, "flame": False, "updated": time.time(),
}


class Reading(BaseModel):
    o2_pct: float | None = None        # from the knob (simulated)
    pressure_psi: float | None = None  # BMP280, or omit
    smoke: float | None = None         # MQ sensor, 0-100 scaled on the ESP32
    temp_c: float | None = None
    dust: float | None = None
    flame: bool | None = None


class Scenario(BaseModel):
    key: str


def risk(state):
    """Simple, explainable fire-risk score (0-100). Not a validated model: it
    combines how flammable the atmosphere is with what the sensors detect."""
    o2 = state["o2_pct"]
    # Atmosphere term: 21% O2 -> 0, 40%+ -> 60. Higher O2 = materials burn more easily.
    atmo = max(0.0, min(60.0, (o2 - 21) / 19 * 60))
    smoke = min(25.0, (state.get("smoke") or 0) / 100 * 25)
    heat = max(0.0, min(15.0, ((state.get("temp_c") or 22) - 30) / 30 * 15))
    flame = 25.0 if state.get("flame") else 0.0
    score = min(100.0, atmo + smoke + heat + flame)
    level = "red" if score >= 60 or state.get("flame") else "yellow" if score >= 30 else "green"
    return {"score": round(score), "level": level,
            "parts": {"atmosphere": round(atmo), "smoke": round(smoke),
                      "heat": round(heat), "flame": round(flame)}}


@app.post("/api/reading")
def post_reading(r: Reading):
    STATE.update({k: v for k, v in r.model_dump().items() if v is not None})
    STATE["source"], STATE["updated"] = "sensor", time.time()
    # Small reply so the ESP32 can set its LEDs/buzzer from it.
    return {"level": risk(STATE)["level"]}


@app.post("/api/scenario")
def set_scenario(s: Scenario):
    STATE.update({"source": "scenario", "scenario": s.key, **SCENARIOS[s.key],
                  "smoke": 0.0, "temp_c": 22.0, "flame": False, "updated": time.time()})
    return get_state()


@app.get("/api/state")
def get_state():
    live = STATE["source"] == "sensor" and time.time() - STATE["updated"] < 10
    return {**STATE, "live": live, "risk": risk(STATE), "scenarios": SCENARIOS}

# ---------- ranking ----------

def closeness(test, o2, p_atm):
    """0..1, how close one NASA test is to the habitat (O2 and pressure)."""
    # Inverse flames: the O2 value is burner gas, not the cabin atmosphere.
    if test["o2_pct"] is None or "burner" in (test.get("o2_note") or ""):
        return None
    d_o2 = abs(test["o2_pct"] - o2) / 20          # 20 points of O2 = "far"
    d_p = abs(test["pressure_atm"] - p_atm) / 0.5 if test["pressure_atm"] is not None else 0.5
    return max(0.0, 1 - (d_o2 ** 2 + d_p ** 2) ** 0.5)


@app.get("/api/rank")
def rank(area: str = "all", limit: int = 30):
    o2, p_atm = STATE["o2_pct"], STATE["pressure_psi"] / PSI_PER_ATM
    results = []
    for inv in CATALOG:
        tests = [t for t in TESTS if t["psi_id"] == inv["id"]]
        scored = [(closeness(t, o2, p_atm), t) for t in tests]
        scored = [x for x in scored if x[0] is not None]
        best = max((s for s, _ in scored), default=0.0)
        # Count original NASA rows (summary rows can expand into several points).
        n_tests = len({(t["table"], t["row"]) for t in tests})
        near = len({(t["table"], t["row"]) for s, t in scored if s > 0.5})
        o2s = [t["o2_pct"] for t in tests if t["o2_pct"] is not None]
        # Score = condition match (50) + crew relevance (30) + area match (20)
        area_match = area == "all" or area in inv.get("areas", [])
        score = 50 * best + 10 * inv.get("crew_relevance", 1) + (20 if area_match else 0)
        if not area_match:
            score *= 0.5
        results.append({
            "id": inv["id"], "acronym": inv["acronym"], "title": inv["title"],
            "doi": inv.get("doi"), "url": inv["url"], "areas": inv.get("areas", []),
            "fuel_kind": inv.get("fuel_kind"), "score": round(score, 1),
            "match": round(best, 2), "tests_total": n_tests, "tests_near": near,
            "o2_range": [min(o2s), max(o2s)] if o2s else None,
            "objectives": (inv.get("objectives") or "")[:400],
            "why": explain(inv, best, near, area_match),
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return {"conditions": {"o2_pct": o2, "pressure_atm": round(p_atm, 3)}, "results": results[:limit]}


def explain(inv, best, near, area_match):
    bits = []
    if best > 0.7:
        bits.append(f"{near} test runs at conditions close to this habitat")
    elif best > 0.3:
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
             "p": t["pressure_atm"], "note": t["o2_note"]}
            for t in TESTS if t["o2_pct"] is not None and t["pressure_atm"] is not None]

# ---------- AI ----------

class Question(BaseModel):
    question: str


def build_context(top):
    lines = []
    for r in top:
        inv = BY_ID[r["id"]]
        sample = [t for t in TESTS if t["psi_id"] == r["id"]][:15]
        lines.append(
            f"### {r['id']} {r['acronym']} - {r['title']} (DOI {inv.get('doi')})\n"
            f"Safety areas: {', '.join(r['areas'])}. Fuel: {r['fuel_kind']}. "
            f"Tests: {r['tests_total']}, near current conditions: {r['tests_near']}. "
            f"O2 range tested: {r['o2_range']}\n"
            f"Objectives: {(inv.get('objectives') or '')[:800]}\n"
            f"Hypothesis: {(inv.get('hypothesis') or '')[:500]}\n"
            f"Impacts: {(inv.get('impacts') or '')[:600]}\n"
            f"Sample test rows (o2_pct, pressure_atm, airflow_cms, fuel, outcome): "
            + "; ".join(f"({t['o2_pct']}, {t['pressure_atm']}, {t['airflow_cms']}, {t['fuel']}, {t['outcome']})"
                        for t in sample))
    return "\n\n".join(lines)


SYSTEM = """You are FlameWatch, a fire-safety assistant for crewed space habitats.
Answer ONLY from the NASA PSI data provided. Cite the PSI ID (e.g. PSI-69) for every
claim. If the data does not cover something (e.g. lunar gravity, or the exact oxygen
level), say so plainly and say what experiment would be needed. Keep answers under
200 words, in plain language for engineers and students."""


@app.post("/api/ask")
def ask(q: Question):
    top = rank(limit=8)["results"]
    st = get_state()
    context = build_context(top)
    prompt = (f"Current habitat: {st['o2_pct']}% O2, {st['pressure_psi']} psi, "
              f"smoke {st['smoke']}, temp {st['temp_c']} C, risk {st['risk']['level']}.\n\n"
              f"NASA PSI data (most relevant first):\n{context}\n\nQuestion: {q.question}")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"answer": "AI is not connected yet (set ANTHROPIC_API_KEY). Most relevant "
                          "experiments right now: " + ", ".join(f"{r['id']} {r['acronym']}" for r in top[:5]),
                "sources": [r["id"] for r in top]}
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model=os.environ.get("FLAMEWATCH_MODEL", "claude-sonnet-5-5"),
        max_tokens=600, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}])
    return {"answer": msg.content[0].text, "sources": [r["id"] for r in top]}

# ---------- frontend ----------

@app.get("/api/health")
def health():
    return {"ok": True, "investigations": len(CATALOG), "tests": len(TESTS)}


# Must be last: serves the dashboard at "/" (API routes above take priority).
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
