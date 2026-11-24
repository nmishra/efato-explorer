# Engine-out after takeoff at KSJC: land straight / turn back / CAPS

Point-mass simulator that asks, for an engine failure after takeoff on each active KSJC runway end
(12L, 12R, 30L, 30R): **from which heights can the airplane safely get back on the departure runway, and where
does CAPS fit into the mix of options?**

> **Study tool only – not operational guidance.** Aircraft numbers are approximate from memory of the
> G5/G6 POH and the KSJC geometry is approximate. Verify everything in `config/*.json` against your POH/AFM and the
> current Chart Supplement, then re-run. Real engine failures involve startle, partial power, turbulence and terrain
> the model doesn't capture.

## Interactive 3D explorer (static, no server)
Open `docs/index.html` in any browser (double-click it). It runs the simulator live in JavaScript (`viewer/sim.js`, a port of
`efato/sim.py`), so you can pick the aircraft, weight, reaction time, bank angle, runway, wind and departure point, drag the
failure altitude, and replay the straight-ahead / turn-back / CAPS paths over live satellite imagery (Esri World Imagery,
loaded from the network; the page still works without it). Rebuild after editing configs: `python3 make_viz.py`.
Aircraft are picked for the Python tools with `EFATO_AIRCRAFT=c172s python run_baseline.py`.

## Run

```bash
cd EFATO_Sim
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python smoke_test.py          # sanity check of the physics
.venv/bin/python run_baseline.py        # decision maps  -> results/map_*.png, baseline_summary_*.md
.venv/bin/python run_sensitivity.py     # min turn-back altitude vs reaction time x bank angle
.venv/bin/python run_montecarlo.py      # option probabilities vs height (12k random cases, ~15 s)
```
Useful flags: `--reaction 4 --bank 45 --bank-after 2 --weight 3400 --isa-dev 10` (baseline),
`--any-runway` (sensitivity: allow landing on the parallel runway).

## Glide and startle
- **Glide:** the drag polar is calibrated per aircraft from two inputs, best-glide speed and L/D at that speed (config `glide`), at the reference weight. Best-glide speed scales with sqrt(weight) and with density (EAS to TAS). The pilot holds that speed; the flight path follows from energy balance (sin γ = −D/W − (dV/dt)/g), so descent angle includes flap drag (50 % flaps costs roughly a point of L/D), extra drag and higher speed in turns, and the wind. Turbine aircraft assume a feathered prop (higher L/D).
- **Startle** (0–1, `--startle`): adds up to 4 s to the reaction delay and makes the pilot hold up to 8 kt above best glide (late pitch-over, poor speed control). Default 0 keeps the published baseline numbers.

## What is modelled
| Piece | How |
|---|---|
| Takeoff | Scaled ground roll + Vy climb to the failure height; wind, weight, density altitude |
| Failure | No thrust. During the **reaction delay** controls are frozen (airplane zooms/decays), then the pilot holds best glide (or 1.15×Vs-in-turn speed when banking) |
| Glide | Drag polar calibrated to Vbg 88 kt and 9:1 L/D (windmilling prop), flap drag, load-factor drag in turns, stall check |
| **S**traight | Land ahead; success if touchdown + landing roll (×1.25) fits in remaining pavement |
| **R**eturn | Bank-limited turn onto the reciprocal; 6 candidate aim points, both turn directions; needs margin ≥ 50 ft, ≤ 30° alignment, and roll-out room *with the takeoff headwind now a tailwind*. Departure runway (`R`) reported separately from "any runway" incl. the parallel |
| **C**APS | Pulled at reaction + 2 s; feasible if height then ≥ 600 ft AGL and ≤ 133 KIAS (config). Canopy drift and on-airport check are in the CSVs |
| "Mixture" | Each (height, runway-remaining) cell gets a code S/R/C/combination; Monte Carlo gives the % of cases where each option works |

Departure points: 11,000 / 8,000 / 6,000 / 4,000 ft remaining (full length vs intersection departures –
check the diagram for real intersections).

## Headline results (baseline: 3,400 lb, ISA+10, flaps 50 %, 4 s reaction + 2 s, 45° bank)
Full-length departure, 10 kt headwind:
- **Straight ahead on the runway works up to ≈ 500 ft AGL** (beyond that you run out of the 11,000 ft). It stops working sooner with shorter remaining runway (≈300 ft at 8,000 ft left, ≈150 ft at 6,000, never at 4,000 in light wind).
- **Turn-back to the departure runway needs ≈ 950–1,100 ft AGL** (≈ 900 with 16 kt wind, ≈ 1,000+ calm/tailwind). Sensitivity: roughly 875–1,075 ft at 45° bank across 2–10 s delays; 30° bank needs ≈ 1,200–1,500 ft; 60° bank buys nothing (needs more speed margin). Landing on the *parallel* runway lowers this ≈ 100–200 ft. With a tailwind on departure (12 ops with NW wind) turn-back often fails entirely on shorter runway.
- **CAPS becomes available at ≈ 600 ft AGL** (config minimum) and covers everything above.
- **The gap**: at short remaining runway, ≈ 200–550 ft AGL has *no* good option (too high for straight ahead, too low for CAPS, nowhere near enough for a turn-back). Monte Carlo: ≈ 46–74 % of failures between 300–600 ft AGL have no runway or CAPS solution; ≈ 600–800 ft is CAPS-or-nothing; turn-back to the departure runway only reaches ~50 % at 1,000 ft and ~80 % by 1,200–1,300 ft.
- Wind/density: stronger headwind lowers the turn-back altitude (shorter ground track), and turn-back is effectively ruled out by tailwind + short remaining runway.

Takeaway the model supports: with full-length departures the best EFATO plan below ~500 ft is straight ahead on
the runway; 600–~1,000 ft is a CAPS decision rather than a turn-back; turn-back only starts to look viable well above
1,000 ft AGL with a fast, disciplined reaction — consistent with common rules of thumb. Intersection departures
widen the "no good option" band.

## Files
- `config/aircraft/*.json` (SR22T, SR22, SR20, C172S, C182T, PA-28 Archer, Bonanza A36, Mooney M20J, DA40, Malibu, M500, M600, M700, PC-12 NGX, Epic E1000 GX – all approximate), `config/airport_ksjc.json` – all editable assumptions (CAPS min altitude, L/D, Vs, runways, winds, departure points).
- `efato/sim.py` – physics and the three options; `efato/analysis.py` – sweeps, Monte Carlo, plots.
- `results/` – maps (`map_<rwy>_<wind>_*.png`), `baseline_*.csv/md`, `min_return_altitude*.png/csv`, `montecarlo_*`.

## Known limitations / next steps
- 30L≡30R and 12L≡12R physically in this model (symmetric); only parallel side and "ahead" terrain notes differ.
- CAPS: level-flight minimum only; no spiral/turn deployment penalty, no canopy-collision/terrain judgement. Raise `min_agl_level_ft` (POH cites ~920 ft for spin) to see the sensitivity.
- No terrain/obstacle model for off-airport landings (notes in `airport_ksjc.json`), no gusts, no partial power, no sim-to-flight validation. Calibrate against flight-test data or your own G1000/Garmin logs (the data_log archives in the parent folder could be used for climb/glide calibration).
