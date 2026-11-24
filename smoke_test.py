"""Quick sanity check of the physics: glide numbers, takeoff distances, and one sweep line."""
import math
from efato.sim import load_config, Scenario, Ctx, evaluate, KT

ac, apt = load_config()
sc = Scenario()
c = Ctx(ac, apt, sc)
print(f"density ratio {c.sig:.3f}  CD0={c.CD0:.4f} k={c.k:.4f} CLmax={c.CLmax:.2f}")
print(f"Vbg(EAS)={c.vbg_eas/KT:.1f} kt  Vs(EAS)={c.vs_eas/KT:.1f} kt  landing roll straight/return = {c.roll_straight:.0f}/{c.roll_return:.0f} ft")
for h in (50, 100, 200, 300, 500, 700, 1000, 1500):
    r = evaluate(c, h)
    print(f"h={h:5d} x_fail={r['x_fail']:6.0f} straight_ok={r['straight_ok']!s:5} td={r['straight_td_x']:7.0f} "
          f"caps={r['caps_ok']!s:5} (h_dep={r['caps_h_deploy']:5.0f}) ret_dep={r['return_dep_ok']!s:5} m={r['return_dep_margin']:8.0f} "
          f"ret_any={r['return_any_ok']!s:5}")
