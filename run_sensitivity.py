"""Minimum height AGL from which a turn-back to the departure runway works, versus pilot
reaction time and bank angle, for several headwinds (full-length departure).

Usage: python run_sensitivity.py [--weight 3400] [--isa-dev 10]
"""
import argparse
import os
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

from efato.sim import Scenario
from efato.analysis import ensure_results, write_csv, _mra_job

ap = argparse.ArgumentParser()
ap.add_argument("--weight", type=float, default=3400.0)
ap.add_argument("--isa-dev", type=float, default=10.0)
ap.add_argument("--bank-after", type=float, default=2.0)
ap.add_argument("--any-runway", action="store_true", help="allow landing on the parallel runway too")
a = ap.parse_args()
out = ensure_results()

reactions = [2, 3, 4, 5, 6, 8, 10]
banks = [30, 45, 60]
winds = [("tailwind 8 kt", -8), ("calm", 0), ("headwind 9 kt", 9), ("headwind 16 kt", 16)]

jobs, keys = [], []
for wn, hw in winds:
    for b in banks:
        for rx in reactions:
            sc = Scenario(runway="30R", remaining_ft=11000.0, headwind_kt=hw, weight_lb=a.weight,
                          isa_dev_c=a.isa_dev, reaction_s=float(rx), bank_after_s=a.bank_after, bank_deg=float(b))
            jobs.append((sc, 100, 3500, 25, 150, a.any_runway))
            keys.append((wn, hw, b, rx))
with ProcessPoolExecutor(mp_context=mp.get_context("fork")) as ex:
    vals = list(ex.map(_mra_job, jobs))
rows = [dict(wind=k[0], headwind_kt=k[1], bank_deg=k[2], reaction_s=k[3], min_return_agl_ft=v) for k, v in zip(keys, vals)]
write_csv(os.path.join(out, "min_return_altitude.csv"), rows)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, len(winds), figsize=(15, 4), sharey=True)
for ax, (wn, hw) in zip(axes, winds):
    for b, col in zip(banks, ["#4393c3", "#1b7837", "#b2182b"]):
        ys = [r["min_return_agl_ft"] for r in rows if r["wind"] == wn and r["bank_deg"] == b]
        ax.plot(reactions, ys, "o-", color=col, label=f"{b}° bank")
    ax.set_title(wn)
    ax.set_xlabel("reaction time (s)")
    ax.grid(alpha=0.3)
axes[0].set_ylabel("min height AGL at failure for\nturn-back to " + ("any runway" if a.any_runway else "departure runway") + " (ft)")
axes[0].legend()
fig.suptitle(f"KSJC full-length departure, {a.weight:.0f} lb, ISA{a.isa_dev:+.0f}C, +{a.bank_after:g}s before banking", fontsize=11)
fig.tight_layout()
suffix = "any" if a.any_runway else "dep"
fig.savefig(os.path.join(out, f"min_return_altitude_{suffix}.png"), dpi=140)

print("min AGL (ft) for a successful turn-back;  rows = bank, cols = reaction s", reactions)
for wn, hw in winds:
    print(f"\n{wn}")
    for b in banks:
        print(f"  {b}°:", [int(r['min_return_agl_ft']) if r['min_return_agl_ft'] == r['min_return_agl_ft'] else None
                           for r in rows if r['wind'] == wn and r['bank_deg'] == b])
