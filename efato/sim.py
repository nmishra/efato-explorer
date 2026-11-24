"""Point-mass EFATO simulator for a Cirrus SR22T.

Frame: x along the takeoff direction measured from brake release (ft), y positive to the
RIGHT of the takeoff direction (ft), h = height AGL (ft).  Heading psi is measured from +x
toward +y (right turn -> psi increases).  The wind is a constant vector (wx, wy).

Model summary
-------------
1. Ground roll + climb at Vy to the failure height (simple scaled POH-style numbers).
2. Engine failure at h_fail.  Reaction delay: controls frozen (constant CL), no thrust, so
   the airplane decays along a phugoid-like path.
3. Controlled glide: pilot holds a target speed (best glide, or turn-margin speed when
   turning); flight path is whatever holds that speed (energy balance), with a 1st-order
   lag.  Drag polar is calibrated so L/D and best-glide speed match config (windmilling prop).
4. Options evaluated from the same failure state:
     STRAIGHT : glide ahead, land on remaining pavement (touchdown + roll <= runway end)
     RETURN   : turn back (bank-limited), land on the reciprocal of the departure runway
                (or, separately, either parallel runway), enough runway behind for the
                landing roll with the (tail)wind
     CAPS     : parachute pulled after recognition + decision time; feasible if height at
                that moment >= configured minimum deployment AGL.  Canopy drift computed.
Everything is deliberately simple and transparent -- this is a decision-support study tool,
not a certified performance model.
"""
import json
import math
import os
from dataclasses import dataclass, replace

from .atmosphere import rho as rho_fn, RHO0

G = 32.174
KT = 1.68781  # kt -> ft/s
CFG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")


def load_config(aircraft=None):
    aircraft = aircraft or os.environ.get("EFATO_AIRCRAFT", "sr22t")
    with open(os.path.join(CFG_DIR, "aircraft", aircraft + ".json")) as f:
        ac = json.load(f)
    with open(os.path.join(CFG_DIR, "airport_ksjc.json")) as f:
        apt = json.load(f)
    return ac, apt


@dataclass(frozen=True)
class Scenario:
    runway: str = "30R"
    remaining_ft: float = 11000.0   # pavement ahead of brake-release point
    headwind_kt: float = 9.0        # along takeoff direction (negative = tailwind)
    crosswind_kt: float = 0.0       # positive = from the right
    weight_lb: float = 3400.0
    isa_dev_c: float = 10.0
    reaction_s: float = 4.0         # engine failure -> pilot takes action (startle + recognition)
    bank_after_s: float = 2.0       # additional seconds after reaction before banking (pushover/decision)
    bank_deg: float = 45.0
    flaps_pct: int = 50
    startle: float = 0.0            # 0..1: adds delay (up to +4 s) and a speed-control error (up to +8 kt above best glide)


def wrap(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


class Ctx:
    """Everything derived once per scenario."""

    def __init__(self, ac, apt, sc: Scenario):
        self.ac, self.apt, self.sc = ac, apt, sc
        self.S = ac["wing_area_ft2"]
        self.W = sc.weight_lb
        Wref = ac["ref_weight_lb"]
        self.Wref = Wref
        self.elev = apt["elevation_ft"]
        self.rho = rho_fn(self.elev, sc.isa_dev_c)
        self.sig = self.rho / RHO0
        self.sqs = math.sqrt(self.sig)
        # drag polar calibrated at best-glide point (ref weight, sea level, flaps 0)
        vbg = ac["glide"]["vbg_kias_ref"] * KT
        ld = ac["glide"]["glide_ratio_ref"]
        cls = 2 * Wref / (RHO0 * self.S * vbg ** 2)
        cd0 = cls / (2 * ld)
        self.k = cd0 / cls ** 2
        fl = str(sc.flaps_pct)
        self.CD0 = cd0 + ac["flap_cd0_delta"][fl]
        vs = ac["stall_kias_ref"][fl] * KT
        self.CLmax = 2 * Wref / (RHO0 * self.S * vs ** 2)
        self.vs_eas = math.sqrt(2 * self.W / (RHO0 * self.S * self.CLmax))
        self.vbg_eas = vbg * math.sqrt(self.W / Wref)
        self.wx = -sc.headwind_kt * KT
        self.wy = -sc.crosswind_kt * KT
        rw = apt["runways"][sc.runway]
        self.rwy_len = rw["length_ft"]
        self.d0 = self.rwy_len - sc.remaining_ft          # pavement behind brake-release point
        self.par_y = rw["parallel_side"] * apt["parallel_spacing_ft"]
        p = ac["pilot"]
        self.turn_margin = p["turn_speed_margin_vs"]
        self.react = sc.reaction_s + 4.0 * sc.startle
        self.speed_bias = 8.0 * KT * sc.startle      # ft/s EAS flown above best-glide speed
        self.roll_rate = math.radians(p["max_roll_rate_deg_s"])
        self.tau_v = p["speed_time_const_s"]
        self.tau_g = p["gamma_time_const_s"]
        self.h_req = p["arrival_margin_req_ft"]
        self.max_align = math.radians(p["max_align_err_deg"])
        self.ld_eff = ld
        # landing roll needed (ft)
        ln = ac["landing"]
        vtd = ln["touchdown_kias"]
        wt = (self.W / Wref)
        base = ln["roll_ref_ft"] * wt / self.sig
        self.roll_straight = base * max(0.5, ((vtd / self.sqs - sc.headwind_kt) / (vtd / self.sqs))) ** 2 * ln["roll_margin_factor"]
        self.roll_return = base * max(0.5, ((vtd / self.sqs + sc.headwind_kt) / (vtd / self.sqs))) ** 2 * ln["roll_margin_factor"]

    def drag(self, V, n_cl):
        """Drag (lb) at TAS V (ft/s) when lift coefficient is n_cl."""
        q = 0.5 * self.rho * V * V
        return q * self.S * (self.CD0 + self.k * n_cl * n_cl)


def takeoff_to_height(c: Ctx, h_fail):
    to = c.ac["takeoff"]
    sc = c.sc
    vr = to["vr_kias"] * KT / c.sqs
    hw = sc.headwind_kt * KT
    roll = (to["ground_roll_ref_ft"] * (c.W / c.Wref) ** to["ground_roll_weight_exp"]
            * c.sig ** (-to["ground_roll_sigma_exp"]) * max(0.4, (vr - hw) / vr) ** 2)
    vy = to["vy_kias"] * KT / c.sqs
    roc = to["roc_ref_fpm"] / 60.0 * (c.Wref / c.W) * c.sig ** 0.6
    g0 = math.asin(min(0.3, roc / vy))
    t_clb = h_fail / roc
    vh = vy * math.cos(g0)
    gs = math.sqrt(max(vh ** 2 - c.wy ** 2, 1.0)) + c.wx
    psi0 = math.asin(max(-1.0, min(1.0, -c.wy / vh)))
    return roll + gs * t_clb, vy, g0, psi0, roll


def delay_phase(c: Ctx, st, td, dt=0.1):
    """Controls frozen (constant CL) after power loss. Returns (state, traj, hit_ground)."""
    x, y, h, V, g, psi = st
    cl0 = c.W * math.cos(g) / (0.5 * c.rho * V * V * c.S)
    traj = [(0.0, x, y, h, V)]
    t = 0.0
    while t < td - 1e-9:
        q = 0.5 * c.rho * V * V
        D = q * c.S * (c.CD0 + c.k * cl0 * cl0)
        L = q * c.S * cl0
        dV = -D * G / c.W - G * math.sin(g)
        dg = (L - c.W * math.cos(g)) * G / (c.W * V)
        vh = V * math.cos(g)
        x += (vh * math.cos(psi) + c.wx) * dt
        y += (vh * math.sin(psi) + c.wy) * dt
        h += V * math.sin(g) * dt
        V += dV * dt
        g += dg * dt
        t += dt
        traj.append((t, x, y, h, V))
        if h <= 0:
            return (x, y, 0.0, V, g, psi), traj, True
    return (x, y, h, V, g, psi), traj, False


def fly(c: Ctx, st, t_off=0.0, aim=None, turn_dir=1, bank_deg=45.0, bank_after_s=2.0,
        record=False, dt=0.25, tmax=300.0):
    """Controlled glide, optionally turning toward aim=(ax, ay).  See module docstring."""
    x, y, h, V, g, psi = st
    phimax = math.radians(bank_deg)
    sqs = c.sqs
    v_cruise = (c.vbg_eas + c.speed_bias) / sqs
    v_turn = max(c.vbg_eas + c.speed_bias, c.turn_margin * c.vs_eas / math.sqrt(math.cos(phimax))) / sqs
    phi = 0.0
    dirn = turn_dir
    t = 0.0
    traj = [(t_off, x, y, h, V)] if record else None
    min_rng = 1e12
    best = None
    out = {"kind": "short", "margin": -1e9, "align_deg": 999.0}
    while t < tmax:
        vx = V * math.cos(g) * math.cos(psi) + c.wx
        vy = V * math.cos(g) * math.sin(psi) + c.wy
        chi = math.atan2(vy, vx)
        phi_cmd = 0.0
        vt = v_cruise
        if aim is not None:
            vt = v_turn
            if t >= bank_after_s:
                e = wrap(math.atan2(aim[1] - y, aim[0] - x) - chi)
                if abs(e) > 2.2:
                    sgn = dirn
                else:
                    sgn = 1 if e > 0 else -1
                    dirn = sgn
                mag = 1.0 if abs(e) > 0.35 else abs(e) / 0.35
                if abs(e) < 0.02:
                    mag = 0.0
                if abs(e) < 0.05:
                    vt = v_cruise
                phi_cmd = sgn * phimax * mag
                # do not bank until there is speed margin for the load factor
                if abs(phi_cmd) > 0.05:
                    n_cmd = 1.0 / math.cos(phi_cmd)
                    if V * sqs < 1.1 * c.vs_eas * math.sqrt(n_cmd):
                        phi_cmd = 0.0
        dphi = phi_cmd - phi
        lim = c.roll_rate * dt
        phi += max(-lim, min(lim, dphi))
        n = 1.0 / math.cos(phi)
        q = 0.5 * c.rho * V * V
        cl = n * c.W * math.cos(g) / (q * c.S)
        if cl > 0.99 * c.CLmax:
            out.update(kind="stall", margin=-1e9)
            break
        D = q * c.S * (c.CD0 + c.k * cl * cl)
        dv_des = (vt - V) / c.tau_v
        sg = max(-0.6, min(0.15, -D / c.W - dv_des / G))
        g_cmd = math.asin(sg)
        g += (g_cmd - g) / c.tau_g * dt
        dV = -D * G / c.W - G * math.sin(g)
        V += dV * dt
        psi += G * math.tan(phi) / V * dt
        vh = V * math.cos(g)
        x += (vh * math.cos(psi) + c.wx) * dt
        y += (vh * math.sin(psi) + c.wy) * dt
        h_prev = h
        h += V * math.sin(g) * dt
        t += dt
        if record:
            traj.append((t_off + t, x, y, h, V))
        if aim is not None:
            rng = math.hypot(aim[0] - x, aim[1] - y)
            if rng < min_rng:
                min_rng = rng
                best = (x, y, h, chi)
            if rng < 150.0 or (rng > min_rng + 60.0 and min_rng < 800.0):
                bx, by, bh, bchi = best
                if bh <= 0:
                    break
                align = abs(wrap(bchi - math.pi))
                out.update(kind="arrive", margin=bh - c.h_req, align_deg=math.degrees(align),
                           x=bx, y=by, h=bh)
                break
        if h <= 0:
            # touchdown / ground contact: linear interpolation to h=0
            f = h_prev / max(h_prev - h, 1e-9)
            xt = x - (1 - f) * (vh * math.cos(psi) + c.wx) * dt
            yt = y - (1 - f) * (vh * math.sin(psi) + c.wy) * dt
            out.update(kind="ground", x=xt, y=yt, h=0.0)
            if aim is not None:
                rng = math.hypot(aim[0] - xt, aim[1] - yt)
                out["margin"] = -rng / c.ld_eff
            break
    out["t"] = t
    out["traj"] = traj
    return out


def evaluate(c: Ctx, h_fail, fast=False, n_aim=6):
    """Evaluate STRAIGHT / RETURN / CAPS from an engine failure at h_fail ft AGL."""
    sc = c.sc
    x_f, V0, g0, psi0, roll = takeoff_to_height(c, h_fail)
    st0 = (x_f, 0.0, float(h_fail), V0, g0, psi0)
    st1, traj1, hit = delay_phase(c, st0, c.react)
    res = {"h_fail": h_fail, "x_fail": x_f, "x_liftoff": roll, "runway_remaining_after_fail": sc.remaining_ft - x_f}

    # ---- STRAIGHT AHEAD ------------------------------------------------------------
    if hit:
        s = {"kind": "ground", "x": st1[0], "y": st1[1], "traj": traj1}
        traj = traj1
    else:
        s = fly(c, st1, t_off=c.react, aim=None, record=True)
        traj = traj1 + s["traj"][1:]
    x_td = s.get("x", float("nan"))
    res["straight_td_x"] = x_td
    res["straight_ok"] = bool(s["kind"] == "ground" and x_td + c.roll_straight <= sc.remaining_ft
                              and x_td >= -c.d0)
    res["straight_runway_left_ft"] = sc.remaining_ft - (x_td + c.roll_straight)

    # ---- CAPS -----------------------------------------------------------------------
    cp = c.ac["caps"]
    t_dep = c.react + (cp["decision_time_after_recognition_s"] if cp else 0.0)
    dep = None
    for row in traj:
        if row[0] >= t_dep - 1e-9:
            dep = row
            break
    if cp is None:
        res.update(caps_ok=False, caps_h_deploy=0.0)
    elif dep is None or dep[3] <= 0:
        res.update(caps_ok=False, caps_h_deploy=0.0)
    else:
        _, xd, yd, hd, Vd = dep
        v_ias = Vd * c.sqs / KT
        ok = hd >= cp["min_agl_level_ft"] and v_ias <= cp["max_deploy_kias"]
        t_can = cp["inflation_time_s"] + max(0.0, hd - cp["altitude_loss_to_inflate_ft"]) / (cp["descent_rate_fpm"] / 60.0)
        xl = xd + cp["forward_travel_ft"] * math.cos(psi0) + c.wx * t_can
        yl = yd + cp["forward_travel_ft"] * math.sin(psi0) + c.wy * t_can
        on_ap = (-c.d0 <= xl <= sc.remaining_ft) and abs(yl) <= c.apt["infield_halfwidth_ft"]
        res.update(caps_ok=bool(ok), caps_h_deploy=hd, caps_land_x=xl, caps_land_y=yl,
                   caps_on_airport=bool(on_ap), caps_drift_ft=c.wx * t_can)

    # ---- RETURN (turn back) ---------------------------------------------------------
    best_dep, best_any = -1e9, -1e9
    x_min = c.roll_return - c.d0
    x_hi = min(x_f, sc.remaining_ft)
    res.update(return_dep_ok=False, return_any_ok=False, return_dep_margin=float("nan"),
               return_any_margin=float("nan"), return_dep_dir=0, return_roll_ft=c.roll_return)
    if not hit and x_hi > x_min:
        cands = [x_min + (x_hi - x_min) * i / (n_aim - 1) for i in range(n_aim)]
        done = False
        for tgt, ay in (("dep", 0.0), ("par", c.par_y)):
            # turn toward the target side first (shorter geometry)
            dirs = (1, -1) if ay >= 0 else (-1, 1)
            for d in dirs:
                for ax in cands:
                    r = fly(c, st1, t_off=c.react, aim=(ax, ay), turn_dir=d,
                            bank_deg=sc.bank_deg, bank_after_s=sc.bank_after_s)
                    if r["kind"] == "arrive":
                        ok = r["margin"] >= 0 and math.radians(r["align_deg"]) <= c.max_align
                        m = r["margin"] if math.radians(r["align_deg"]) <= c.max_align else -1e9
                    else:
                        ok, m = False, r["margin"]
                    if tgt == "dep":
                        if m > best_dep:
                            best_dep = m
                            res["return_dep_dir"] = d
                        if ok:
                            res["return_dep_ok"] = True
                    if m > best_any:
                        best_any = m
                    if ok:
                        res["return_any_ok"] = True
                        if fast and tgt == "dep":
                            done = True
                            break
                if done:
                    break
            if done:
                break
        res["return_dep_margin"] = best_dep
        res["return_any_margin"] = best_any
    return res
