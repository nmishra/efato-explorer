# Engine-out after takeoff: land straight / turn back / CAPS

A point-mass simulator and an interactive 3D explorer that ask, for a single-engine airplane departing any runway:
**from which heights can the airplane get back on the departure runway, and where does CAPS (or landing straight ahead) fit?**

> **Study tool, not operational guidance.** Aircraft performance comes only from POH numbers: the SR22T profile
> was read from the G5 POH (page references inside `config/aircraft/sr22t.json`); any other aircraft is entered by you
> from your POH. Nothing is filled in from memory. The model's own assumptions are listed below.

## Interactive explorer (static, no server)
Open `docs/index.html` in any browser, or use the GitHub Pages site. It runs the simulator live in JavaScript
(`viewer/sim.js`, a port of `efato/sim.py`).
- **Airport:** type any ICAO/FAA identifier. Runways, headings, lengths, elevation and parallel runways are read live from the
  OurAirports database (public domain, FAA-derived). KSJC is bundled so the page works offline.
- **Visualization fence:** a 1-4 NM (default 3) ring and wall around the airport over live satellite imagery (Esri World Imagery).
- **Aircraft:** built-in profiles read from POHs (SR22T G5, Cessna 172S, Cessna 182T, Epic E1000 GX; see `_sources` in each file), or **Enter / edit POH data** to type your own airplane's numbers, save them in the
  browser, export or import them as JSON. Exported JSON works with the Python tools too.
- **Pilot and conditions:** weight, reaction time, startle (adds delay and speed error), bank, headwind, crosswind, departure point,
  failure height. See the straight-ahead, turn-back and CAPS paths overlaid, and fly each one.

## Python tools
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python smoke_test.py          # sanity check
.venv/bin/python run_baseline.py        # decision maps -> results/map_*.png, baseline_summary_*.md
.venv/bin/python run_sensitivity.py     # min turn-back altitude vs reaction time x bank angle
.venv/bin/python run_montecarlo.py      # option probabilities vs height
python3 make_viz.py                     # rebuild docs/index.html after changing configs
```
Wing area is optional (it cancels once L/D and stall speed are given). Other aircraft: copy `config/aircraft/TEMPLATE.json.txt` to `config/aircraft/<id>.json`, fill every null from your POH, then
`EFATO_AIRCRAFT=<id> .venv/bin/python run_baseline.py`. Flags: `--reaction --bank --bank-after --weight --isa-dev --startle`.

## Where the numbers come from
| Input | Source |
|---|---|
| Aircraft speeds, climb, takeoff/landing roll, stall speeds, best glide and L/D, CAPS speed / altitude loss / descent rate | **POH** (SR22T G5 P/N 13772-005; see `_sources` in the profile) or your entry in the form |
| CAPS minimum altitude | **Your choice** (600 ft AGL here). The POH sets no minimum, reports level-flight loss under 400 ft and advises 2,000 ft AGL when possible |
| Runways, headings, lengths, elevation | OurAirports `runways.csv` |
| Wind, weight, reaction time, startle, bank, departure point | Scenario inputs you choose |
| **Model assumptions (not data)** | Flap drag increments, 1.25x landing-roll margin, pilot roll rate and speed-control time constants, 2 s CAPS decision time, 8 s inflation, 600 ft forward travel, ground-roll weight/density scaling (derived from the POH where two weights are given), startle = up to +4 s and +8 kt |

## How glide is computed
The drag polar is calibrated per aircraft from the best-glide speed and L/D at that speed (POH: 92 KIAS, 8.6:1 for the SR22T).
Best-glide speed scales with sqrt(weight) and density. After the reaction delay the pilot holds that speed and the descent angle
follows from energy balance, so flaps, turn load factor, startle speed error and wind all change the glide.

## Headline results (SR22T G5 POH values, 3,400 lb, ISA+10, 4 s reaction + 2 s, 45 deg bank, 600 ft CAPS minimum)
Full-length KSJC departure, 10 kt headwind:
- **Straight ahead on the runway works up to about 600 ft AGL.** With less runway ahead it stops sooner (about 400 ft with 8,000 ft left, 250 ft with 6,000, 100 ft with 4,000).
- **Turn-back to the departure runway needs about 1,100 ft AGL** (about 1,000 with a 20 kt headwind, 1,350 calm). Across 2-10 s reaction times at 45 deg bank the minimum is roughly 1,025-1,300 ft; 30 deg bank needs about 1,450-1,750 ft; 60 deg bank is no better than 45. Landing on the parallel runway lowers it by 100-150 ft. A tailwind or a short runway can rule turn-back out entirely.
- **CAPS is available from about 650 ft AGL** with the 600 ft minimum.
- **The gap:** with 8,000 ft or less ahead, roughly 450-600 ft AGL has no good option. Monte Carlo (12,000 mixed cases): 28-59 % of failures between 300 and 600 ft AGL have neither a runway landing nor CAPS; 600-700 ft is largely CAPS-or-nothing; turn-back to the departure runway reaches 50 % of cases only around 1,200 ft.

## Files
`config/` (aircraft profiles and airport), `efato/` (physics, sweeps, plots), `viewer/` (browser app and `sim.js`), `docs/index.html` (built page),
`results/` (maps, CSVs, plots), `make_viz.py`.

## Limits
No terrain or obstacle model beyond the satellite view, no gusts or partial power, constant wind, a 2-D point-mass model, KIAS treated as EAS.
CAPS uses level-flight altitude loss only; spiral or turning deployments need more height.
