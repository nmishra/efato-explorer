"""Generate config/aircraft/*.json from a compact table.
ALL VALUES ARE APPROXIMATE (from memory of typical POH figures) -- verify against the POH/AFM for your airplane."""
import json, os
base = {
  "takeoff_exp": {"ground_roll_weight_exp": 1.8, "ground_roll_sigma_exp": 1.0},
  "flap_cd0_delta": {"0": 0.0, "50": 0.012, "100": 0.040},
  "pilot": {"turn_speed_margin_vs": 1.15, "max_roll_rate_deg_s": 15, "speed_time_const_s": 2.0,
            "gamma_time_const_s": 1.0, "arrival_margin_req_ft": 50, "max_align_err_deg": 30},
}
CAPS = {"max_deploy_kias": 133, "min_agl_level_ft": 600, "altitude_loss_to_inflate_ft": 400, "descent_rate_fpm": 1700,
        "inflation_time_s": 8, "forward_travel_ft": 600, "decision_time_after_recognition_s": 2.0}
# id, name, maxW, S, Vr, Vy, ROC, groundroll, Vbg, L/D, Vs0/50/100, landroll, Vtd, caps, turbo
T = [
 ("sr22t","Cirrus SR22T",3600,144.9,78,96,1150,1450,88,9.0,(74,69,64),1700,70,True,True),
 ("sr22","Cirrus SR22",3600,144.9,77,96,1270,1400,88,9.0,(74,69,64),1700,70,True,False),
 ("sr20","Cirrus SR20",3050,144.9,73,92,850,1000,85,9.0,(65,60,56),1400,64,True,False),
 ("c172s","Cessna 172S Skyhawk",2550,174,55,74,730,960,68,9.0,(53,48,47),1000,55,False,False),
 ("c182t","Cessna 182T Skylane",3100,174,55,80,924,850,80,8.5,(54,50,49),1150,58,False,False),
 ("pa28","Piper PA-28-181 Archer",2550,170,60,76,667,1050,76,8.5,(55,52,50),1100,58,False,False),
 ("a36","Beechcraft Bonanza A36",3650,181,70,98,1030,1150,100,10.0,(66,62,58),1500,70,False,False),
 ("m20j","Mooney M20J",2740,167,63,88,900,1050,88,10.0,(59,55,52),1500,66,False,False),
 ("da40","Diamond DA40",2535,145.3,59,68,1000,1000,73,10.5,(49,47,45),1100,52,False,False),
 ("malibu","Piper PA-46 Malibu / Mirage",4300,175,72,100,1100,1450,100,10.0,(69,64,61),1400,72,False,False),
 ("m500","Piper M500 (turboprop)",5092,175,75,110,1400,1500,100,12.0,(74,68,62),1500,78,False,True),
 ("m600","Piper M600 (turboprop)",6000,200,80,120,1200,1700,105,12.0,(76,70,64),1700,80,False,True),
 ("m700","Piper M700 Fury (turboprop)",6000,200,80,120,1450,1700,105,12.0,(76,70,64),1700,80,False,True),
 ("pc12","Pilatus PC-12 NGX (turboprop)",10450,279.4,80,125,1700,2000,110,13.0,(85,75,67),1800,82,False,True),
 ("e1000","Epic E1000 GX (turboprop)",7000,152,85,135,1800,1700,120,12.0,(80,73,68),1700,85,False,True),
]
out = os.path.join(os.path.dirname(__file__), "..", "config", "aircraft")
for (i,n,w,S,vr,vy,roc,gr,vbg,ld,vs,lr,td,caps,turbo) in T:
    j = {"_note":"APPROXIMATE values -- verify against your POH/AFM.", "id":i, "name":n, "max_weight_lb":w, "ref_weight_lb":w,
         "wing_area_ft2":S,
         "takeoff":{"vr_kias":vr,"vy_kias":vy,"roc_ref_fpm":roc,"ground_roll_ref_ft":gr,
                    "ground_roll_weight_exp":1.8,"ground_roll_sigma_exp":0.8 if turbo else 1.0},
         "glide":{"vbg_kias_ref":vbg,"glide_ratio_ref":ld},
         "stall_kias_ref":{"0":vs[0],"50":vs[1],"100":vs[2]},
         "flap_cd0_delta":base["flap_cd0_delta"],
         "landing":{"roll_ref_ft":lr,"touchdown_kias":td,"roll_margin_factor":1.25},
         "caps":CAPS if caps else None,
         "pilot":base["pilot"]}
    json.dump(j, open(os.path.join(out, i+".json"), "w"), indent=1)
json.dump([t[0] for t in T], open(os.path.join(out, "index.json"), "w"))
print("wrote", len(T), "aircraft")
