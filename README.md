# FlameWatch

**Fire risk for a Moon base, checked against NASA's fire experiments in space.**

Team Odyssey-1, NASA Space Apps Challenge 2026, challenge: *Flame in Freefall*.

**Try it:** [flamewatch.onrender.com](https://flamewatch.onrender.com). Pick a habitat and press **Simulate a fire**. The free server sleeps when nobody's using it, so the first load can take up to a minute.

---

## Why we built it

NASA plans to give Moon base crews air with **34% oxygen at 8.2 psi**, compared with 21% on Earth and on the International Space Station. The richer air lets astronauts start moonwalks sooner, but it also makes things catch fire more easily and burn faster. Apollo 1 showed in 1967 how deadly a fire in oxygen-rich air can be.

NASA has run a lot of fire experiments in space. The results sit in its Physical Sciences Informatics (PSI) database, split across **24 separate combustion investigations**, each with its own files, units and column names. Nothing tells a designer which of them apply to the air in their habitat, or which conditions nobody has tested.

When we put every test run on one chart, we found that only **32 of 1,738** NASA test runs come close to Moon base air, and none of those burned the fabrics and plastics a cabin is made of. PSI also has no fire data from lunar gravity yet. The question a Moon base designer most needs answered is the one the public data covers least.

FlameWatch puts that evidence in one place and shows where it runs out.

## What it does

1. **Pick a habitat.** Choose a Moon base, the ISS, a pressurized rover or a spacesuit, and see it in 3D.
2. **Read the fire risk.** A 0–100 score shows how dangerous the current conditions are, split into four parts: oxygen-rich air, smoke, heat and flame. Each part is explained on screen.
3. **See the NASA evidence.** The 24 NASA experiments are ranked by how many of their test runs were close to your habitat's air (within 4 points of oxygen and 30% of the pressure). Open any experiment to see what it burned and what it found, or compare up to three side by side.
4. **Find the gaps.** A chart plots every NASA test run by oxygen and pressure, and draws a box around your habitat. An empty box means that air hasn't been tested.
5. **Ask a question.** An AI assistant answers questions like "Which materials are riskiest at this oxygen level?" using NASA's data, and names the experiment behind each point.
6. **Watch a fire play out.** "Simulate a fire" runs a 30-second scripted fire in the 3D habitat: smoke builds, the vent closes, the alarm goes off, the crew leave, the hatch seals and CO₂ puts the fire out. Each habitat gets its own script. In the spacesuit, for example, there's no vent to close and nowhere to go.
7. **Download the data.** The matching test runs export as a CSV for anyone building a fire model.

## The sensor box

We built a hardware prototype of early-warning equipment for a habitat module. It's an ESP32 with a smoke input, a temperature sensor, a motion sensor (is the crew still inside?), a distance sensor (is the hatch closed?), and a dial that sets the oxygen level. It sends readings to the dashboard every second, and the dashboard sends back what to do:

- the LEDs show green, yellow or red,
- the buzzer sounds on a Warning,
- a servo closes the vent when there's smoke or a heat rise, because in low gravity the airflow is what feeds a fire,
- if someone's still in the module, it tells the crew to get out before suppression starts.

The heat trigger gets more sensitive as oxygen goes up, because fires start more easily in richer air.

## Who it's for

- **Habitat engineers** can check a cabin's air against NASA test runs before a design is locked in.
- **NASA fire researchers** can see which conditions have never been tested, and plan the next experiment.
- **Crews and mission control** get a working concept for equipment that warns early and acts on its own.

The same physics applies on Earth wherever air is enriched with oxygen, such as hospital oxygen therapy and hyperbaric chambers.

## How it meets the challenge

NASA set three goals for *Flame in Freefall*. FlameWatch covers all three:

| NASA's goal | How FlameWatch covers it |
| --- | --- |
| Relevance to crewed habitats | Habitat presets, a live risk score, experiments ranked by how close they are to that habitat's air |
| Data for predictive modeling | One cleaned table of 2,186 NASA test runs, a comparison view and a CSV export |
| Next-generation safety equipment | The sensor box with automatic vent control, and a chart of what still needs testing |

## Built on NASA data

Every number on the dashboard traces back to NASA:

- **NASA PSI:** all 24 combustion investigations, downloaded through PSI's public API and cleaned into one table of 2,186 test runs. Each run keeps a link to its NASA file and row.
- **Beyond PSI:** PSI has no lunar-gravity fire data, so we added three NASA studies:
  - Olson and Ferkul, 2012: in lunar gravity, Mylar kept burning at 15.6% oxygen. On Earth it needed 21.2%.
  - The LUCI flight, 2025: acrylic flames spread at 1.5 mm/s in lunar gravity, against 4.0 mm/s on Earth.
  - Urban et al., 2025: NASA's suggested oxygen safety margin for materials on the Moon (up to 2.3 points for polycarbonate).

  Flames spread more slowly in lunar gravity, but materials can keep burning at lower oxygen. That means Earth's standard flammability test may not be strict enough for a Moon base.

## What it doesn't do

We'd rather say this plainly than have a judge find it:

- The risk score is a simple, transparent rule of thumb, not a validated fire model.
- The box's oxygen level comes from a dial, not an oxygen sensor.
- The heat trigger is set low (a few degrees of rise) so a warm hand can set it off in a demo. A real system would rely on smoke detection.
- NASA tests that don't record pressure (BASS, Saffire) are assumed to be at normal cabin pressure.
- NASA's Saffire-VI burned fabric near Moon base conditions in 2023–24, but those results aren't in PSI yet, so they aren't in our matching.

## Run it yourself

```bash
pip install -r requirements.txt
python scripts/fetch_psi.py && python scripts/clean.py
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000. Deployment, the AI usage limits and the sensor box's data format are in [docs/TECHNICAL.md](docs/TECHNICAL.md).

## Sources

- [NASA Physical Sciences Informatics (PSI)](https://psi.nasa.gov). Please cite each experiment's PSI DOI when using the data.
- [Olson and Ferkul, NASA, 2012: partial-gravity flammability limits](https://ntrs.nasa.gov/citations/20130010991)
- [Ferkul et al., NASA, 2025: LUCI lunar-gravity flame spread](https://ntrs.nasa.gov/api/citations/20250010653/downloads/ASGSR%202025-LUCI-Ferkul-Presentation-v2-20250010653.pdf)
- [Urban et al., NASA, 2025: Solid Fuel Ignition Testing for Lunar Applications](https://ntrs.nasa.gov/citations/20250002114)
- [NASA, 2025: 28.5% oxygen alternate habitat atmosphere](https://ntrs.nasa.gov/citations/20250004535)
- [NASA Saffire-VI report](https://ntrs.nasa.gov/citations/20240002981)
- Built with FastAPI, Three.js, Chart.js and Anthropic's Claude API. Hosted on Render.
