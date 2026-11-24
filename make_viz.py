"""Build the shareable, fully static explorer (no server, no data files): docs/index.html
The simulator runs live in the browser (viewer/sim.js is a port of efato/sim.py).
Built-in aircraft: only profiles in config/aircraft/ whose numbers come from a POH (listed in BUILTIN).
Usage: python make_viz.py
"""
import json, os
here = os.path.dirname(os.path.abspath(__file__))
cfg = os.path.join(here, "config")
BUILTIN = ["sr22t", "c172s", "c182t", "e1000"]
apt = json.load(open(os.path.join(cfg, "airport_ksjc.json")))
# KSJC fallback in the same shape the browser builds from the OurAirports runway database
rw = {}
for k, v in apt["runways"].items():
    g = apt["geo"][k]
    rw[k] = {"lat": g["lat"], "lon": g["lon"], "hdg": g["hdg"], "length_ft": v["length_ft"],
             "opp": {"12L": "30R", "12R": "30L", "30L": "12R", "30R": "12L"}[k],
             "par": v["parallel"], "par_y": v["parallel_side"] * apt["parallel_spacing_ft"]}
fallback = {"icao": "KSJC", "elevation_ft": apt["elevation_ft"], "arp": apt["arp"],
            "infield_halfwidth_ft": apt["infield_halfwidth_ft"], "runways": rw}
data = {"order": BUILTIN, "aircraft": {i: json.load(open(os.path.join(cfg, "aircraft", i + ".json"))) for i in BUILTIN},
        "airport_fallback": fallback}
rd = lambda *p: open(os.path.join(here, *p)).read()
page = rd("viewer", "viewer_template.html")
page = page.replace("/*__EMBED__*/", "window.EFATO_CFG=" + json.dumps(data, separators=(",", ":")) + ";")
page = page.replace("/*__SIM__*/", rd("viewer", "sim.js"))
page = page.replace('<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>', "<script>" + rd("viewer", "vendor", "three.min.js") + "</script>")
page = page.replace('<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>', "<script>" + rd("viewer", "vendor", "OrbitControls.js") + "</script>")
html = "<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'></head><body>" + page + "</body></html>"
os.makedirs(os.path.join(here, "docs"), exist_ok=True)
open(os.path.join(here, "docs", "index.html"), "w").write(html)
print("docs/index.html: %.2f MB" % (len(html) / 1e6))
