"""Disentangle the unsafe ORB fallback change from the ECC-direction correction.

Triggered by wrong-board controls after the locked main study. These validation
controls cannot be used to claim a newly optimized held-out detector result.
"""
import json
import time
import cv2
import numpy as np
import experiments as e

direction_only=e.fork_module(e.REG_FIXED,'app.cv.research_registration_direction_only',[
    ('            continue\n    else:\n        best_poor = next((a for a in attempts if a.quality == "poor"), None)',
     '            break\n    else:\n        best_poor = None')])
ladder_only=e.fork_module(e.reg,'app.cv.research_registration_ladder_only',[
    ('            break\n    else:\n        best_poor = None',
     '            continue\n    else:\n        best_poor = next((a for a in attempts if a.quality == "poor"), None)')])
methods={'legacy':e.reg,'ecc_direction_only':direction_only,'orb_ladder_only':ladder_only,'ecc_plus_orb':e.REG_FIXED}
rows=[]
for seed in [200001,200002,300001,300002]:
    a=e.gray(e.Board(seed).render(illum_seed=seed,noise_seed=seed+1)[0])
    b=e.gray(e.Board(seed+900000).render(illum_seed=seed+2,noise_seed=seed+3)[0])
    for name,method in methods.items():
        r=method.register(a,b)
        rows.append(dict(board=seed,control='wrong_board',treatment=name,accepted=r.ok,metrics=r.metrics))
for seed in range(500001,500005):
    d=e.scene(seed,'pose')
    for name,method in methods.items():
        r=method.register(d['ref'],d['test'])
        points=np.array([[40.,40.],[860.,40.],[40.,560.],[860.,560.],[450.,300.]],np.float32)
        error=None
        if r.warp is not None:
            q=cv2.transform(cv2.transform(points[None],d['pose']),r.warp)[0]
            error=float(np.linalg.norm(points-q,axis=1).mean())
        rows.append(dict(board=seed,control='new_board_pose',treatment=name,accepted=r.ok,pose_error_px=error,metrics=r.metrics))
fixed_local=e.fork_module(e.rt,'app.cv.research_region_tools_local_fix',[
    ('realigned = cv2.warpAffine(test_crop, warp, (w, h))',
     'realigned = cv2.warpAffine(test_crop, warp, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)'),
    ('after = float(cv2.absdiff(ref_crop, realigned).mean())',
     'after = 255.0 * float(cv2.absdiff(ref_crop, realigned).mean())'),
    ('    if reduction > 0.7:', '    if cc < 0.7:\n        summary = "Local registration unreliable; retain review."\n    elif reduction > 0.7:')])
rng=np.random.default_rng(8)
ref=cv2.GaussianBlur(rng.integers(15,240,(240,320),dtype=np.uint8),(7,7),0)
cv2.putText(ref,'PCB 26',(35,125),cv2.FONT_HERSHEY_SIMPLEX,1.5,230,3)
test=ref.copy();cv2.circle(test,(150,120),9,20,-1)
local=[]
for label,image in [('injected_defect',test),('translation_only',cv2.warpAffine(ref,np.array([[1,0,1.5],[0,1,-1]],np.float32),(320,240)))]:
    ctx=e.rt.ToolContext(ref,image,image,np.ones_like(ref)*255,cv2.absdiff(ref,image),1-e.det.local_ncc(ref,image))
    for name,module in [('legacy',e.rt),('units_direction_reliability_fix',fixed_local)]:
        o=module.tool_local_realignment(ctx,'probe',[138,108,24,24])
        local.append(dict(control=label,treatment=name,metrics=o.metrics,supports_defect=o.supports_defect))
src=rng.uniform(0,200,(60,1,2)).astype(np.float32);dst=src+np.array([3.,-2.],np.float32)
estimators={}
for name in ['estimateAffinePartial2D','estimateAffine2D','findHomography']:
    try:
        warp,inliers=getattr(cv2,name)(src,dst,method=cv2.USAC_MAGSAC)
        estimators[name]=dict(supported=warp is not None,inliers=int(inliers.sum()) if inliers is not None else None)
    except cv2.error as exc:estimators[name]=dict(supported=False,error=str(exc))
result=dict(registration=rows,local_verifier=local,usac_capability=estimators,
            caveat='Post-study failure isolation; not a second untouched test set for detector selection.')
e.dump('registration-followup.json',result)
print(json.dumps(result,indent=2))
