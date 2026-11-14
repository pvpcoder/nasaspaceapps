# FlameWatch

Habitat fire-safety dashboard built on NASA PSI microgravity combustion data.
NASA Space Apps 2026, *Flame in Freefall*.

## Setup (once, ~5 min)

```bash
pip install -r requirements.txt
python scripts/fetch_psi.py     # downloads NASA metadata + experimental tables (needs internet)
python scripts/clean.py         # builds data/tests.csv + data/catalog.json
```

Read the report `clean.py` prints. It lists which column it picked for oxygen, pressure and airflow in each experiment. If a guess is wrong, fix it in `OVERRIDES` at the top of `scripts/clean.py` and re-run.

## Run

```bash
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000. `--host 0.0.0.0` lets the ESP32 reach it on the same Wi-Fi via your laptop's IP (e.g. `http://192.168.1.23:8000`).

### Turn on the AI chat

```bash
export ANTHROPIC_API_KEY=your-key        # Windows: set ANTHROPIC_API_KEY=your-key
pip install anthropic
```

Without a key, the chat still replies with the top-ranked experiments.

## ESP32 contract

POST JSON to `http://<laptop-ip>:8000/api/reading` about once a second. Every field is optional; send what you have.

```json
{"o2_pct": 34.0, "pressure_psi": 8.2, "smoke": 42, "temp_c": 27.5, "dust": 12, "flame": false}
```

- `o2_pct`: from the knob, mapped to 21–40
- `smoke`: MQ sensor scaled to 0–100 on the ESP32
- `pressure_psi`: BMP280 reading (hPa × 0.0145), or leave it out

The reply is `{"level": "green" | "yellow" | "red"}`. Use it to drive the LEDs and buzzer.

If no reading arrives for 10 seconds, the dashboard falls back to the scenario dropdown.

## Test without hardware

```bash
curl -X POST localhost:8000/api/reading -H "Content-Type: application/json" \
  -d '{"o2_pct":34,"pressure_psi":8.2,"smoke":60,"temp_c":35}'
```

## Files

| Path | What |
| --- | --- |
| `scripts/fetch_psi.py` | Pulls NASA PSI combustion data through its public API |
| `scripts/clean.py` | Maps messy NASA columns onto shared fields; tags safety area, fuel and crew relevance |
| `backend/app.py` | API: live readings, risk score, ranking, gaps data, AI chat |
| `frontend/` | Dashboard (plain HTML/JS, Chart.js bundled so it works offline) |

## Honest caveats (say these in the demo)

- The oxygen value from the box is simulated with a knob.
- The risk score is a simple, transparent heuristic, not a validated fire model.
- Tests without a pressure column (BASS, Saffire) are assumed to be at ~1 atm cabin air.
- Inverse-flame O₂ (CFI-G, Flame Design) is burner gas, not cabin air, so it's excluded from matching.
- PSI has no partial-gravity (lunar) combustion data yet.

Cite PSI DOIs when using the data (PSI requirement).
