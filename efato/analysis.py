"""Shared sweep / Monte-Carlo / plotting helpers."""
import csv
import math
import os
import random
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

from .sim import Scenario, Ctx, evaluate, load_config

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")

CODE_LABEL = {
    0: "none (no runway landing, CAPS too low)",
    1: "S  straight ahead on runway",
    2: "R  turn-back to dep. runway",
    3: "S+R",
    4: "C  CAPS only",
    5: "S+C",
    6: "R+C",
    7: "S+R+C",
}
CODE_COLOR = {0: "#b2182b", 1: "#a6dba0", 2: "#fdb863", 3: "#5aae61", 4: "#4393c3", 5: "#92c5de", 6: "#8073ac", 7: "#1b7837"}


def code_of(r):
    return int(r["straight_ok"]) * 1 + int(r["return_dep_ok"]) * 2 + int(r["caps_ok"]) * 4


def ensure_results():
    os.makedirs(RESULTS, exist_ok=True)
    return RESULTS


# ---------------------------------------------------------------- workers (top-level for pickling)
def _eval_job(args):
    sc, h, fast = args
    ac, apt = load_config()
    c = Ctx(ac, apt, sc)
    r = evaluate(c, h, fast=fast)
    r.update(runway=sc.runway, remaining_ft=sc.remaining_ft, headwind_kt=sc.headwind_kt,
             crosswind_kt=sc.crosswind_kt, weight_lb=sc.weight_lb, isa_dev_c=sc.isa_dev_c,
             reaction_s=sc.reaction_s, startle=sc.startle, bank_after_s=sc.bank_after_s, bank_deg=sc.bank_deg, flaps_pct=sc.flaps_pct)
    return r


def pmap(jobs, workers=None, chunk=64):
    workers = workers or os.cpu_count() or 1
    if workers <= 1 or len(jobs) < 50:
        return [_eval_job(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("fork")) as ex:
        return list(ex.map(_eval_job, jobs, chunksize=chunk))


def write_csv(path, rows):
    if not rows:
        return
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})


# ---------------------------------------------------------------- baseline decision maps
def runs_of(vals, hs, flag):
    """Contiguous [h_lo, h_hi] intervals where vals==flag."""
    out, start = [], None
    for v, h in zip(vals, hs):
        if v == flag and start is None:
            start = h
        if v != flag and start is not None:
            out.append((start, prev))
            start = None
        prev = h
    if start is not None:
        out.append((start, hs[-1]))
    return out


def plot_decision_map(rows, hs, remainings, title, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm
    from matplotlib.patches import Patch
    grid = []
    for rem in remainings:
        line = []
        for h in hs:
            r = next(x for x in rows if x["remaining_ft"] == rem and x["h_fail"] == h)
            line.append(code_of(r))
        grid.append(line)
    cmap = ListedColormap([CODE_COLOR[i] for i in range(8)])
    norm = BoundaryNorm(list(range(9)), cmap.N)
    fig, ax = plt.subplots(figsize=(11, 3.6 + 0.35 * len(remainings)))
    dh = hs[1] - hs[0]
    ax.imshow(grid, aspect="auto", cmap=cmap, norm=norm, origin="lower",
              extent=[hs[0] - dh / 2, hs[-1] + dh / 2, -0.5, len(remainings) - 0.5], interpolation="nearest")
    ax.set_yticks(range(len(remainings)))
    ax.set_yticklabels([f"{int(r):,} ft left" for r in remainings])
    ax.set_xlabel("Height AGL at engine failure (ft)")
    ax.set_title(title, fontsize=11)
    handles = [Patch(color=CODE_COLOR[i], label=CODE_LABEL[i]) for i in range(8) if any(i in g for g in grid)]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


# ---------------------------------------------------------------- min return altitude
def min_return_altitude(sc, h_lo=100, h_hi=3000, step=25, need_run=150, any_runway=False):
    """Lowest h_fail from which turn-back works and keeps working for the next `need_run` ft."""
    ac, apt = load_config()
    c = Ctx(ac, apt, sc)
    key = "return_any_ok" if any_runway else "return_dep_ok"
    h = h_lo
    first = None
    while h <= h_hi:
        ok = evaluate(c, h, fast=True)[key]
        if ok and first is None:
            first = h
        if not ok:
            first = None
        elif first is not None and h - first >= need_run:
            return first
        h += step
    return float("nan")


def _mra_job(args):
    return min_return_altitude(*args)


# ---------------------------------------------------------------- Monte Carlo
def sample_scenario(rng, apt, remainings_w, startle=0.0):
    rw = rng.choice(list(apt["runways"].keys()))
    w = rng.choice(apt["default_wind_scenarios"][rw])
    hw = rng.gauss(w["headwind_kt"], 2.5)
    xw = rng.gauss(w["crosswind_kt"], 2.5)
    rem = rng.choices([r for r, _ in remainings_w], weights=[p for _, p in remainings_w])[0]
    react = min(12.0, max(1.5, rng.lognormvariate(math.log(4.2), 0.35)))
    return Scenario(runway=rw, remaining_ft=float(rem), headwind_kt=hw, crosswind_kt=xw,
                    weight_lb=rng.uniform(3000, 3600), isa_dev_c=rng.gauss(8, 7),
                    reaction_s=react, bank_after_s=rng.uniform(1.0, 4.0),
                    bank_deg=rng.choice([30, 35, 40, 45, 50]), flaps_pct=rng.choices([0, 50], weights=[0.2, 0.8])[0], startle=startle)
