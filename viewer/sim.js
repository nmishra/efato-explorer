// JavaScript port of efato/sim.py + efato/viz_export.py (keep the two in sync).
// Frame: x along takeoff direction from brake release (ft), y to the right (ft), h AGL (ft).
const G=32.174, KT=1.68781, RHO0=0.0023769;
const rhoF=(alt,dev)=>{const T=288.15-0.0019812*alt+dev,p=101325*Math.pow(1-6.87559e-6*alt,5.25588);return p/(287.05*T)*0.00194032;};
const wrap=a=>{while(a>Math.PI)a-=2*Math.PI;while(a<-Math.PI)a+=2*Math.PI;return a;};
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

class Ctx{
  constructor(ac,apt,sc){
    this.ac=ac;this.apt=apt;this.sc=sc;this.S=ac.wing_area_ft2;this.W=sc.weight_lb;const Wref=ac.ref_weight_lb;this.Wref=Wref;
    this.rho=rhoF(apt.elevation_ft,sc.isa_dev_c);this.sig=this.rho/RHO0;this.sqs=Math.sqrt(this.sig);
    const vbg=ac.glide.vbg_kias_ref*KT,ld=ac.glide.glide_ratio_ref,cls=2*Wref/(RHO0*this.S*vbg*vbg),cd0=cls/(2*ld);
    this.k=cd0/(cls*cls);const fl=String(sc.flaps_pct);this.CD0=cd0+ac.flap_cd0_delta[fl];
    const vs=ac.stall_kias_ref[fl]*KT;this.CLmax=2*Wref/(RHO0*this.S*vs*vs);
    this.vs_eas=Math.sqrt(2*this.W/(RHO0*this.S*this.CLmax));this.vbg_eas=vbg*Math.sqrt(this.W/Wref);
    this.wx=-sc.headwind_kt*KT;this.wy=-sc.crosswind_kt*KT;
    const rw=apt.runways[sc.runway];this.rwy_len=rw.length_ft;this.d0=this.rwy_len-sc.remaining_ft;
    this.par_y=rw.parallel_side*apt.parallel_spacing_ft;
    const p=ac.pilot;this.turn_margin=p.turn_speed_margin_vs;this.react=sc.reaction_s+4*(sc.startle||0);this.speed_bias=8*KT*(sc.startle||0);this.roll_rate=p.max_roll_rate_deg_s*Math.PI/180;
    this.tau_v=p.speed_time_const_s;this.tau_g=p.gamma_time_const_s;this.h_req=p.arrival_margin_req_ft;
    this.max_align=p.max_align_err_deg*Math.PI/180;this.ld_eff=ld;
    const ln=ac.landing,vtd=ln.touchdown_kias,wt=this.W/Wref,base=ln.roll_ref_ft*wt/this.sig,vt=vtd/this.sqs;
    this.vtd_tas=vt;
    this.roll_straight=base*Math.pow(Math.max(.5,(vt-sc.headwind_kt)/vt),2)*ln.roll_margin_factor;
    this.roll_return=base*Math.pow(Math.max(.5,(vt+sc.headwind_kt)/vt),2)*ln.roll_margin_factor;
  }
}

function takeoffToHeight(c,hFail){
  const to=c.ac.takeoff,sc=c.sc,vr=to.vr_kias*KT/c.sqs,hw=sc.headwind_kt*KT;
  const roll=to.ground_roll_ref_ft*Math.pow(c.W/c.Wref,to.ground_roll_weight_exp)*Math.pow(c.sig,-to.ground_roll_sigma_exp)*Math.pow(Math.max(.4,(vr-hw)/vr),2);
  const vy=to.vy_kias*KT/c.sqs,roc=to.roc_ref_fpm/60*(c.Wref/c.W)*Math.pow(c.sig,.6);
  const g0=Math.asin(Math.min(.3,roc/vy)),tClb=hFail/roc,vh=vy*Math.cos(g0);
  const gs=Math.sqrt(Math.max(vh*vh-c.wy*c.wy,1))+c.wx,psi0=Math.asin(clamp(-c.wy/vh,-1,1));
  return {xf:roll+gs*tClb,V0:vy,g0,psi0,roll,roc,vr};
}

function delayPhase(c,st,td,dt=.1){
  let [x,y,h,V,g,psi]=st;const cl0=c.W*Math.cos(g)/(.5*c.rho*V*V*c.S);const traj=[[0,x,y,h,V]];let t=0;
  while(t<td-1e-9){
    const q=.5*c.rho*V*V,D=q*c.S*(c.CD0+c.k*cl0*cl0),L=q*c.S*cl0;
    const dV=-D*G/c.W-G*Math.sin(g),dg=(L-c.W*Math.cos(g))*G/(c.W*V),vh=V*Math.cos(g);
    x+=(vh*Math.cos(psi)+c.wx)*dt;y+=(vh*Math.sin(psi)+c.wy)*dt;h+=V*Math.sin(g)*dt;V+=dV*dt;g+=dg*dt;t+=dt;
    traj.push([t,x,y,h,V]);
    if(h<=0)return {st:[x,y,0,V,g,psi],traj,hit:true};
  }
  return {st:[x,y,h,V,g,psi],traj,hit:false};
}

function fly(c,st,o){
  o=o||{};const tOff=o.tOff||0,aim=o.aim||null,bankDeg=o.bankDeg||45,bankAfter=o.bankAfter==null?2:o.bankAfter,record=!!o.record,dt=.25,tmax=300;
  let [x,y,h,V,g,psi]=st;const phimax=bankDeg*Math.PI/180,sqs=c.sqs,vCruise=(c.vbg_eas+c.speed_bias)/sqs;
  const vTurn=Math.max(c.vbg_eas+c.speed_bias,c.turn_margin*c.vs_eas/Math.sqrt(Math.cos(phimax)))/sqs;
  let phi=0,dirn=o.turnDir||1,t=0,minRng=1e12,best=null;
  const traj=record?[[tOff,x,y,h,V]]:null;const out={kind:'short',margin:-1e9,align_deg:999};
  while(t<tmax){
    const vx=V*Math.cos(g)*Math.cos(psi)+c.wx,vy=V*Math.cos(g)*Math.sin(psi)+c.wy,chi=Math.atan2(vy,vx);
    let phiCmd=0,vt=vCruise;
    if(aim){vt=vTurn;
      if(t>=bankAfter){
        const e=wrap(Math.atan2(aim[1]-y,aim[0]-x)-chi);let sgn;
        if(Math.abs(e)>2.2)sgn=dirn;else{sgn=e>0?1:-1;dirn=sgn;}
        let mag=Math.abs(e)>.35?1:Math.abs(e)/.35;if(Math.abs(e)<.02)mag=0;if(Math.abs(e)<.05)vt=vCruise;
        phiCmd=sgn*phimax*mag;
        if(Math.abs(phiCmd)>.05){const n=1/Math.cos(phiCmd);if(V*sqs<1.1*c.vs_eas*Math.sqrt(n))phiCmd=0;}
      }}
    const lim=c.roll_rate*dt;phi+=clamp(phiCmd-phi,-lim,lim);
    const n=1/Math.cos(phi),q=.5*c.rho*V*V,cl=n*c.W*Math.cos(g)/(q*c.S);
    if(cl>.99*c.CLmax){out.kind='stall';out.margin=-1e9;break;}
    const D=q*c.S*(c.CD0+c.k*cl*cl),dvDes=(vt-V)/c.tau_v,sg=clamp(-D/c.W-dvDes/G,-.6,.15),gCmd=Math.asin(sg);
    g+=(gCmd-g)/c.tau_g*dt;V+=(-D*G/c.W-G*Math.sin(g))*dt;psi+=G*Math.tan(phi)/V*dt;
    const vh=V*Math.cos(g);x+=(vh*Math.cos(psi)+c.wx)*dt;y+=(vh*Math.sin(psi)+c.wy)*dt;
    const hPrev=h;h+=V*Math.sin(g)*dt;t+=dt;
    if(record)traj.push([tOff+t,x,y,h,V]);
    if(aim){const rng=Math.hypot(aim[0]-x,aim[1]-y);
      if(rng<minRng){minRng=rng;best=[x,y,h,chi];}
      if(rng<150||(rng>minRng+60&&minRng<800)){const [bx,by,bh,bchi]=best;if(bh<=0)break;
        out.kind='arrive';out.margin=bh-c.h_req;out.align_deg=Math.abs(wrap(bchi-Math.PI))*180/Math.PI;out.x=bx;out.y=by;out.h=bh;break;}}
    if(h<=0){const f=hPrev/Math.max(hPrev-h,1e-9),xt=x-(1-f)*(vh*Math.cos(psi)+c.wx)*dt,yt=y-(1-f)*(vh*Math.sin(psi)+c.wy)*dt;
      out.kind='ground';out.x=xt;out.y=yt;out.h=0;if(aim)out.margin=-Math.hypot(aim[0]-xt,aim[1]-yt)/c.ld_eff;break;}
  }
  out.t=t;out.traj=traj;return out;
}

function decimate(rows,step){const out=[];let last=-1e9;rows.forEach((r,i)=>{if(r[0]-last>=step||i===rows.length-1){out.push([Math.round(r[0]*10)/10,Math.round(r[1]),Math.round(r[2]),Math.max(0,Math.round(r[3]))]);last=r[0];}});return out;}

// Full evaluation. opts.paths -> include decimated trajectories; opts.fast -> stop turn-back search at first success.
function evaluate(c,hFail,opts){
  opts=opts||{};const sc=c.sc,ac=c.ac,rec=!!opts.paths,fast=!!opts.fast;
  const T=takeoffToHeight(c,hFail),xf=T.xf;
  const st0=[xf,0,hFail,T.V0,T.g0,T.psi0];
  const d1=delayPhase(c,st0,c.react),st1=d1.st,traj1=d1.traj,hit=d1.hit;
  const res={h:hFail,xf};
  // straight
  let base,s;
  if(hit){s={kind:'ground',x:st1[0],y:st1[1]};base=traj1;}
  else{s=fly(c,st1,{tOff:c.react,record:true});base=traj1.concat(s.traj.slice(1));}
  const xtd=s.x;
  res.straight={ok:s.kind==='ground'&&xtd+c.roll_straight<=sc.remaining_ft&&xtd>=-c.d0,td:Math.round(xtd),roll:Math.round(c.roll_straight),left:Math.round(sc.remaining_ft-(xtd+c.roll_straight))};
  if(rec){const pts=decimate(base,1.5),e=pts[pts.length-1];
    pts.push([Math.round((e[0]+2*c.roll_straight/c.vtd_tas)*10)/10,e[1]+Math.round(c.roll_straight),e[2],0]);res.straight.pts=pts;}
  // CAPS
  const cp=ac.caps;res.caps={ok:false,hd:0,pts:[],land:null,onap:false,drift:0,available:!!cp};
  if(cp){
    const tDep=c.react+cp.decision_time_after_recognition_s;const dep=base.find(r=>r[0]>=tDep-1e-9);
    if(dep&&dep[3]>0){
      const [,xd,yd,hd,Vd]=dep,vias=Vd*c.sqs/KT,ok=hd>=cp.min_agl_level_ft&&vias<=cp.max_deploy_kias;
      const tCan=cp.inflation_time_s+Math.max(0,hd-cp.altitude_loss_to_inflate_ft)/(cp.descent_rate_fpm/60);
      const xl=xd+cp.forward_travel_ft*Math.cos(T.psi0)+c.wx*tCan,yl=yd+cp.forward_travel_ft*Math.sin(T.psi0)+c.wy*tCan;
      const onap=xl>=-c.d0&&xl<=sc.remaining_ft&&Math.abs(yl)<=c.apt.infield_halfwidth_ft;
      Object.assign(res.caps,{ok,hd:Math.round(hd),land:[Math.round(xl),Math.round(yl)],onap,drift:Math.round(c.wx*tCan)});
      if(rec&&hd>5){const ti=cp.inflation_time_s,pre=decimate(base.filter(r=>r[0]<=tDep+1e-9),1.5);
        res.caps.pts=pre.concat([[Math.round((tDep+ti)*10)/10,Math.round(xd+cp.forward_travel_ft*Math.cos(T.psi0)+c.wx*ti),Math.round(yd+cp.forward_travel_ft*Math.sin(T.psi0)+c.wy*ti),Math.max(0,Math.round(hd-cp.altitude_loss_to_inflate_ft))],
          [Math.round((tDep+tCan)*10)/10,Math.round(xl),Math.round(yl),0]]);}
    }
  }
  // return
  const best={dep:null,par:null};res.ret_any=false;
  const xMin=c.roll_return-c.d0,xHi=Math.min(xf,sc.remaining_ft);
  if(!hit&&xHi>xMin){
    const cands=[];for(let i=0;i<6;i++)cands.push(xMin+(xHi-xMin)*i/5);
    let done=false;
    for(const [tgt,ay] of [['dep',0],['par',c.par_y]]){
      const dirs=ay>=0?[1,-1]:[-1,1];
      for(const d of dirs){for(const ax of cands){
        const q=fly(c,st1,{tOff:c.react,aim:[ax,ay],turnDir:d,bankDeg:sc.bank_deg,bankAfter:sc.bank_after_s,record:rec});
        let ok,m;
        if(q.kind==='arrive'){const good=q.align_deg*Math.PI/180<=c.max_align;ok=q.margin>=0&&good;m=good?q.margin:-1e6;}else{ok=false;m=q.margin;}
        const cur=best[tgt];
        if(!cur||(ok&&!cur.ok)||(ok===cur.ok&&m>cur.m))best[tgt]={ok,m,ax,ay,q};
        if(ok){res.ret_any=true;if(fast&&tgt==='dep'){done=true;break;}}
      }if(done)break;}
      if(done)break;
    }
  }
  for(const k of ['dep','par']){const b=best[k];
    if(!b){res['ret_'+k]=null;continue;}
    const o={ok:b.ok,margin:b.m>-1e5?Math.round(b.m):null,aim:[Math.round(b.ax),Math.round(b.ay)],need:Math.round(c.roll_return)};
    if(rec){const pts=decimate(traj1.concat(b.q.traj.slice(1)),1.5);
      if(b.ok){const e=pts[pts.length-1];pts.push([Math.round((e[0]+2*c.roll_return/c.vtd_tas)*10)/10,Math.round(e[1]-c.roll_return),e[2],0]);}o.pts=pts;}
    res['ret_'+k]=o;}
  res.code=(res.straight.ok?1:0)+(res.ret_dep&&res.ret_dep.ok?2:0)+(res.caps.ok?4:0);
  if(rec){ // climb path for display
    const tRoll=2*T.roll/T.vr,tClb=hFail/T.roc,climb=[];
    for(const f of [0,.35,.7,1])climb.push([Math.round(tRoll*f*10)/10,Math.round(T.roll*f*f),0,0]);
    for(let i=1;i<=10;i++){const f=i/10;climb.push([Math.round((tRoll+tClb*f)*10)/10,Math.round(T.roll+(xf-T.roll)*f),0,Math.round(hFail*f)]);}
    res.climb=climb;res.tc=climb[climb.length-1][0];}
  return res;
}
if(typeof module!=='undefined')module.exports={Ctx,evaluate,takeoffToHeight};
