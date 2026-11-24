"""Decision maps: for each KSJC runway end x wind scenario x departure point, which options
(S = land straight ahead on remaining runway, R = turn back to the departure runway,
C = CAPS) work as a function of height at engine failure.

Usage:  python run_baseline.py [--reaction 4] [--bank 45] [--bank-after 2] [--weight 3400]
                               [--isa-dev 10] [--hmax 1800] [--step 50]
"""
import argparse
import os

from efato.sim import Scenario, load_config
from efato.analysis import (pmap, write_csv, ensure_results, plot_decision_map, code_of, runs_of)

ap = argparse.ArgumentParser()
ap.add_argument("--reaction", type=float, default=4.0, help="s from failure to pilot action")
ap.add_argument("--bank", type=float, default=45.0)
ap.add_argument("--bank-after", type=float, default=2.0, help="extra s before banking")
ap.add_argument("--weight", type=float, default=3400.0)
ap.add_argument("--isa-dev", type=float, default=10.0)
ap.add_argument("--flaps", type=int, default=50, choices=[0, 50])
ap.add_argument("--startle", type=float, default=0.0, help="0..1 startle factor (adds up to 4 s delay and up to 8 kt speed error)")
ap.add_argument("--hmax", type=int, default=1800)
ap.add_argument("--step", type=int, default=50)
a = ap.parse_args()

ac, apt = load_config()
out = ensure_results()
hs = list(range(a.step, a.hmax + 1, a.step))
rems = apt["departure_points"]["remaining_ft"]

jobs, meta = [], []
for rwy, winds in apt["default_wind_scenarios"].items():
    for w in winds:
        for rem in rems:
            sc = Scenario(runway=rwy, remaining_ft=float(rem), headwind_kt=w["headwind_kt"],
                          crosswind_kt=w["crosswind_kt"], weight_lb=a.weight, isa_dev_c=a.isa_dev,
                          reaction_s=a.reaction, bank_after_s=a.bank_after, bank_deg=a.bank, flaps_pct=a.flaps, startle=a.startle)
            for h in hs:
                jobs.append((sc, h, False))
                meta.append(w["name"])
rows = pmap(jobs)
for r, name in zip(rows, meta):
    r["wind"] = name
    r["code"] = code_of(r)
tag = f"rx{a.reaction:g}_bank{a.bank:g}"
write_csv(os.path.join(out, f"baseline_{tag}.csv"), rows)

lines = [f"# Baseline decision summary ({tag}, W={a.weight:.0f} lb, ISA{a.isa_dev:+.0f}C, flaps {a.flaps}%)\n",
         "Reaction = s from failure to pilot action; +bank-after s before banking.  Heights are AGL at failure.\n",
         "| Runway | Wind | Rwy left at brake release | Straight-ahead OK up to | Turn-back to dep. rwy OK from | Turn-back to ANY rwy OK from | CAPS OK from | Heights with NO option |",
         "|---|---|---|---|---|---|---|---|"]
for rwy, winds in apt["default_wind_scenarios"].items():
    for w in winds:
        sub = [r for r in rows if r["runway"] == rwy and r["wind"] == w["name"]]
        title = f"KSJC {rwy}  |  {w['name']}  |  reaction {a.reaction:g}s + {a.bank_after:g}s, bank {a.bank:g}°, {a.weight:.0f} lb"
        plot_decision_map(sub, hs, [float(x) for x in rems], title,
                          os.path.join(out, f"map_{rwy}_{w['name'].replace(' ', '_')}_{tag}.png"))
        for rem in rems:
            s = sorted([r for r in sub if r["remaining_ft"] == rem], key=lambda r: r["h_fail"])
            def first(key):
                for r in s:
                    if r[key]:
                        return r["h_fail"]
                return None
            s_ok = [r["h_fail"] for r in s if r["straight_ok"]]
            s_txt = f"{max(s_ok)} ft" if s_ok else "never"
            if s_ok and max(s_ok) == hs[-1]:
                s_txt = f">={hs[-1]} ft"
            none_runs = runs_of([r["code"] for r in s], hs, 0)
            none_txt = ", ".join(f"{lo}-{hi}" for lo, hi in none_runs) or "-"
            fr = lambda v: f"{v} ft" if v else "-"
            lines.append(f"| {rwy} | {w['name']} | {int(rem):,} | {s_txt} | {fr(first('return_dep_ok'))} | "
                         f"{fr(first('return_any_ok'))} | {fr(first('caps_ok'))} | {none_txt} |")
with open(os.path.join(out, f"baseline_summary_{tag}.md"), "w") as f:
    f.write("\n".join(lines) + "\n")
print("\n".join(lines))
print(f"\nWrote maps + CSV to {out}")
