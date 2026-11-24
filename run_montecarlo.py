"""Monte Carlo over weight, density, wind, departure point, pilot delay, bank and flaps.
Reports, versus height at failure, the probability that each option (and any option) is
available -- i.e. the 'mixture' of straight-ahead / turn-back / CAPS.

Usage: python run_montecarlo.py [--n 12000] [--seed 1] [--hmax 1800]
"""
import argparse
import os
import random

from efato.sim import load_config
from efato.analysis import pmap, write_csv, ensure_results, sample_scenario, code_of

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=12000)
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--startle", type=float, default=0.0)
ap.add_argument("--hmin", type=int, default=50)
ap.add_argument("--hmax", type=int, default=1800)
a = ap.parse_args()

ac, apt = load_config()
out = ensure_results()
rng = random.Random(a.seed)
REM = [(11000, 0.55), (8000, 0.20), (6000, 0.15), (4000, 0.10)]   # departure-point mix (edit to taste)
jobs = []
for _ in range(a.n):
    sc = sample_scenario(rng, apt, REM, a.startle)
    jobs.append((sc, rng.uniform(a.hmin, a.hmax), True))
rows = pmap(jobs)
for r in rows:
    r["code"] = code_of(r)
write_csv(os.path.join(out, "montecarlo_samples.csv"), rows)

BIN = 100
edges = list(range(0, a.hmax + 1, BIN))
tab = []
for lo, hi in zip(edges[:-1], edges[1:]):
    s = [r for r in rows if lo <= r["h_fail"] < hi]
    if not s:
        continue
    n = len(s)
    f = lambda fn: sum(1 for r in s if fn(r)) / n
    tab.append(dict(h_lo=lo, h_hi=hi, n=n,
                    straight=f(lambda r: r["straight_ok"]), ret_dep=f(lambda r: r["return_dep_ok"]),
                    ret_any=f(lambda r: r["return_any_ok"]), caps=f(lambda r: r["caps_ok"]),
                    any_runway=f(lambda r: r["straight_ok"] or r["return_dep_ok"]),
                    any_option=f(lambda r: r["straight_ok"] or r["return_dep_ok"] or r["caps_ok"]),
                    caps_only=f(lambda r: r["caps_ok"] and not (r["straight_ok"] or r["return_dep_ok"])),
                    none=f(lambda r: r["code"] == 0)))
write_csv(os.path.join(out, "montecarlo_by_height.csv"), tab)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
mid = [(t["h_lo"] + t["h_hi"]) / 2 for t in tab]
fig, ax = plt.subplots(figsize=(10, 5.2))
for key, lab, col, ls in [("straight", "Straight ahead on remaining runway", "#5aae61", "-"),
                          ("ret_dep", "Turn-back to departure runway", "#e08214", "-"),
                          ("caps", "CAPS deployable (>= min AGL)", "#2166ac", "-"),
                          ("any_option", "ANY option (S, R or C)", "black", "--"),
                          ("none", "NO option", "#b2182b", "-")]:
    ax.plot(mid, [100 * t[key] for t in tab], ls, color=col, lw=2, label=lab)
ax.set_xlabel("Height AGL at engine failure (ft)")
ax.set_ylabel("% of simulated cases where option works")
ax.set_ylim(-2, 102)
ax.grid(alpha=0.3)
ax.legend(fontsize=9, loc="center right")
ax.set_title(f"EFATO at KSJC -- Monte Carlo, n={a.n}", fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(out, "montecarlo_options_vs_height.png"), dpi=140)

# stacked mix chart
fig, ax = plt.subplots(figsize=(10, 4.8))
from efato.analysis import CODE_COLOR, CODE_LABEL
bottom = [0.0] * len(tab)
for code in (7, 5, 3, 1, 6, 2, 4, 0):
    vals = []
    for t in tab:
        s = [r for r in rows if t["h_lo"] <= r["h_fail"] < t["h_hi"]]
        vals.append(100 * sum(1 for r in s if r["code"] == code) / len(s))
    ax.bar(mid, vals, width=BIN * 0.95, bottom=bottom, color=CODE_COLOR[code], label=CODE_LABEL[code])
    bottom = [b + v for b, v in zip(bottom, vals)]
ax.set_xlabel("Height AGL at engine failure (ft)")
ax.set_ylabel("% of cases")
ax.legend(fontsize=8, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.15), frameon=False)
ax.set_title("Mixture of available options (S=straight, R=return, C=CAPS)", fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(out, "montecarlo_option_mixture.png"), dpi=140)

print(f"{'AGL band':>12} {'n':>5} {'straight':>9} {'return':>7} {'retANY':>7} {'CAPS':>6} {'any':>6} {'none':>6}")
for t in tab:
    print(f"{t['h_lo']:>5}-{t['h_hi']:<6} {t['n']:>5} {100*t['straight']:8.0f}% {100*t['ret_dep']:6.0f}% {100*t['ret_any']:6.0f}% "
          f"{100*t['caps']:5.0f}% {100*t['any_option']:5.0f}% {100*t['none']:5.0f}%")
