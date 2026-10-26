"""Isolated research; imports production read-only, never invokes persistent tools.

Pixel inference never receives annotations or known pose. Board-group splits and
all fixed treatments are specified in PLAN.md before held-out results.
"""
from __future__ import annotations
import argparse
import copy
import dataclasses
import hashlib
import importlib.util
import json
import platform
import sys
import time
import types
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT)]
import cv2
import numpy as np
from app.cv import registration as reg
from app.cv import detection as det
from app.cv import region_tools as rt
from app.cv import verification as ver
from app.cv.preprocess import preprocess, PreprocessParams
from app.agent import policy
from tools.generate_dataset import Board
from evaluation.benchmark import score_variant, iou

# Freeze the study's original algorithms now that production has advanced.
# String-based ablations must keep targeting the measured baseline rather
# than silently changing their meaning (or failing) after a production fix.
def _study_baseline(name):
    path = HERE / 'baseline' / f'{name}.py'
    spec = importlib.util.spec_from_file_location(f'app.cv.study_baseline_{name}', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reg = _study_baseline('registration')
rt = _study_baseline('region_tools')
rt.register = reg.register
ver = _study_baseline('verification')

cv2.setNumThreads(1)
cv2.setRNGSeed(260026)
OUT = HERE / 'results'
OUT.mkdir(exist_ok=True)
TYPES = ['open_circuit','short_circuit','mousebite','spur','spurious_copper','pinhole']
PROFILES = ['clean','mild','gain','glare','pose','blur_noise']
TREATMENTS = ['legacy','symmetric','symmetric_ecc','small_morph','no_median',
              'bilateral','clahe_detection','robust_gain','multiplicative','erode_valid']

def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False))

def env():
    return dict(python=sys.version, opencv=cv2.__version__, numpy=np.__version__,
                platform=platform.platform(), threads=cv2.getNumThreads(),
                synthetic=True, device='local CPU', seed=260026)

def fork_module(original, name, changes):
    source = Path(original.__file__).read_text()
    for before, after in changes:
        assert before in source, f'Prototype replacement no longer matches source: {before}'
        source = source.replace(before, after)
    module = types.ModuleType(name)
    module.__file__ = str(HERE / (name.split('.')[-1] + '.py'))
    module.__package__ = original.__package__
    sys.modules[name] = module
    (HERE / Path(module.__file__).name).write_text(source)
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    return module

def corrected_registration():
    # Keep the public convention test->reference; invert only at ECC boundaries.
    return fork_module(reg, 'app.cv.research_registration', [
        ('else np.asarray(init, np.float32).copy()', 'else cv2.invertAffineTransform(np.asarray(init, np.float32))'),
        ('# warp now maps full-res test -> reference',
         'warp = cv2.invertAffineTransform(warp)\n    # ECC yields reference->test; convert to public forward convention'),
        ('np.ascontiguousarray(warp.astype(np.float32).reshape(2, 3)),',
         'np.ascontiguousarray(cv2.invertAffineTransform(warp.astype(np.float32)).reshape(2, 3)),'),
        ('return refined.astype(np.float32), float(cc)',
         'return cv2.invertAffineTransform(refined).astype(np.float32), float(cc)'),
        ('            break\n    else:\n        best_poor = None',
         '            continue\n    else:\n        best_poor = next((a for a in attempts if a.quality == "poor"), None)'),
    ])

REG_FIXED = corrected_registration()

def robust_gain(ref, test):
    good = (ref>8)&(ref<245)&(test>8)&(test<245)
    a, b = test[::4,::4][good[::4,::4]].astype(float), ref[::4,::4][good[::4,::4]].astype(float)
    if len(a)<100: return test.astype(np.float32)
    keep = np.ones(len(a),bool)
    coef=np.array([1.,0.])
    for _ in range(4):
        coef=np.linalg.lstsq(np.c_[a[keep],np.ones(keep.sum())],b[keep],rcond=None)[0]
        residual=b-(coef[0]*a+coef[1]); med=np.median(residual)
        scale=1.4826*np.median(np.abs(residual-med))+1.
        keep=np.abs(residual-med)<3*scale
    return test.astype(np.float32)*np.clip(coef[0],.5,2)+np.clip(coef[1],-60,60)

DET_GAIN = fork_module(det,'app.cv.research_detection_gain',[
    ('    test_f = aligned_test_gray.astype(np.float32)',
     '    test_f = robust_gain(ref_gray, aligned_test_gray)')])
DET_GAIN.robust_gain=robust_gain
DET_MULT = fork_module(det,'app.cv.research_detection_mult',[
    ('test_norm = test_f - mean_test + mean_ref',
     'test_norm = test_f * np.clip((mean_ref+1.0)/(mean_test+1.0), 0.5, 2.0)')])
DET_ERODE = fork_module(det,'app.cv.research_detection_erode',[
    ('obs_valid = cv2.dilate(obs_valid,', 'obs_valid = cv2.erode(obs_valid,')])

def gray(bgr): return cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)

def warp_detection(raw, registration, treatment):
    if treatment=='legacy': return registration.warped_test
    if treatment=='no_median': image=raw
    elif treatment=='bilateral': image=cv2.bilateralFilter(raw,5,20,3)
    else: image=preprocess(raw,for_registration=False)
    return cv2.warpAffine(image,registration.warp,(raw.shape[1],raw.shape[0]))

def reference_detection(raw, treatment):
    if treatment=='no_median': return raw
    if treatment=='bilateral': return cv2.bilateralFilter(raw,5,20,3)
    return preprocess(raw,for_registration=False)

def detect(ref, test, valid, treatment):
    p=det.DetectionParams()
    if treatment=='small_morph': p=det.DetectionParams(morph_open_ksize=1,morph_close_ksize=3,morph_bridge_ksize=3)
    if treatment=='clahe_detection':
        cl=cv2.createCLAHE(2.,(8,8));ref,test=cl.apply(ref),cl.apply(test)
    method={'robust_gain':DET_GAIN,'multiplicative':DET_MULT,'erode_valid':DET_ERODE}.get(treatment,det)
    return method.detect_candidates(ref,test,valid,p)

def matching(gt, cands, threshold):
    # Maximum-cardinality bipartite matching, preferring higher IoU neighbors.
    adj=[sorted([j for j,g in enumerate(gt) if iou(c['bbox'],g['bbox'])>=threshold],
                key=lambda j:-iou(c['bbox'],gt[j]['bbox'])) for c in cands]
    owner={}
    def augment(i,seen):
        for j in adj[i]:
            if j in seen: continue
            seen.add(j)
            if j not in owner or augment(owner[j],seen): owner[j]=i;return True
        return False
    for i in range(len(cands)): augment(i,set())
    tp=len(owner);fp=len(cands)-tp;fn=len(gt)-tp
    return dict(tp=tp,fp=fp,fn=fn, matched_gt=sorted(owner),
                precision=tp/(tp+fp) if tp+fp else 1.,
                recall=tp/(tp+fn) if tp+fn else 1.,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.)

def fixed_verdict(candidates, quality):
    out=copy.deepcopy(candidates)
    for c in out:
        d,m=c['difference_score'],c['structural_mismatch_score']
        if c['touches_invalid_warp_region']: status='NOT_EVALUABLE'
        elif d>=ver.STRONG_DIFF and m>=ver.STRONG_MISMATCH and c['evidence_quality_score']>=.35: status='CONFIRMED_DEFECT'
        elif c['illumination_suspect']: status='CLEARED'
        elif d>=ver.MODERATE_DIFF or m>=ver.MODERATE_MISMATCH: status='LIKELY_DEFECT'
        else: status='NEEDS_REVIEW'
        c['status']=status
    return out

def adaptive(candidates,ctx,quality,has_view):
    # Same planner, region tools and rule table, no store/REST/artifact side effects.
    cands={f'R{i+1:02}':dict(copy.deepcopy(c),status='SUSPECTED',tools_used=[],evidence=[],notes=[])
           for i,c in enumerate(candidates)}
    used=0;iterations=0;errors=[]
    while iterations<24:
        iterations+=1
        action=policy.choose_action(cands,quality,has_view)
        if action is None: break
        rid,tool,*_=action;c=cands[rid]
        if tool!='verify' and used>=12: break
        if tool=='verify':
            status,label,basis,notes=ver.verify_candidate(c,c['evidence'],quality)
            c.update(status=status,label=label,label_basis=basis,notes=notes)
        elif tool=='request_additional_view':
            c['tools_used'].append(tool);used+=1;c['status']='NEEDS_REVIEW'
        else:
            try: ev=rt.TOOL_FUNCTIONS[tool](ctx,rid,c['bbox'])
            except Exception as exc:
                errors.append(dict(tool=tool,error=str(exc)));c['status']='NEEDS_REVIEW';used+=1;continue
            c['tools_used'].append(tool);used+=1
            c['evidence'].append(dict(source_tool=ev.tool,evidence_kind=ev.evidence_kind,
                                     supports_defect=ev.supports_defect,metrics=ev.metrics,honesty=ev.honesty))
    for c in cands.values():
        if c['status'] not in policy.TERMINAL_STATUSES: c['status']='NEEDS_REVIEW'
    return list(cands.values()),used,errors

def scene(seed,profile):
    board=Board(seed)
    # Equal render-noise seeds are not used between observations.
    ds=[dict(kind=TYPES[(seed+j*2)%6],seed=seed*31+j) for j in range(3)]
    ref,_=board.render(illum_seed=seed+11,noise_seed=seed+12)
    kw=dict(defects=[] if profile=='clean' else ds,illum_seed=seed+21,noise_seed=seed+22)
    if profile=='glare':kw['glare']=(300+(seed%250),300,170.)
    if profile=='blur_noise':kw['noise_sigma']=12.
    test,ann=board.render(**kw)
    v2,_=board.render(defects=[] if profile=='clean' else ds,illum_seed=seed+31,noise_seed=seed+32)
    pose=np.eye(2,3,dtype=np.float32)
    if profile=='gain': test=np.clip(test.astype(float)*1.28-12,0,255).astype(np.uint8)
    if profile=='blur_noise':test=cv2.GaussianBlur(test,(5,5),1.1)
    if profile=='pose':
        pose=cv2.getRotationMatrix2D((450,300),1.25,1.005).astype(np.float32);pose[:,2]+=np.array([4.,-3.])
        test=cv2.warpAffine(test,pose,(900,600))
    # Original annotation boxes are in design/reference space; transformed capture
    # is warped back there for inspection. Known pose is evaluation-only.
    return dict(ref=gray(ref),test=gray(test),view=gray(v2) if profile!='gain' else None,
                gt=[d.to_json() for d in ann],pose=pose,board=seed,profile=profile)

def save_scene(d,split):
    path=HERE/'data'/split/f"b{d['board']}_{d['profile']}";path.mkdir(parents=True,exist_ok=True)
    for k in ['ref','test','view']:
        if d[k] is not None:cv2.imwrite(str(path/f'{k}.png'),d[k])
    meta={k:d[k] for k in ['board','profile','gt']};meta['reference_to_capture_pose']=d['pose'].tolist()
    meta['has_independent_synthetic_capture']=d['view'] is not None
    (path/'annotations.json').write_text(json.dumps(meta,indent=2))

def evaluate_scene(d,treatments,with_agent):
    ref,test=d['ref'],d['test'];registrations={};rows=[]
    for key,method in [('legacy',reg),('fixed',REG_FIXED)]:
        t0=time.perf_counter();r=method.register(ref,test);elapsed=time.perf_counter()-t0
        registrations[key]=(r,elapsed)
    for treatment in treatments:
        key='legacy' if treatment in ['legacy','symmetric'] else 'fixed'
        r,regtime=registrations[key];t0=time.perf_counter()
        candidates=[];dettime=0.;invalid_pixels=0
        rr=reference_detection(ref,treatment)
        if r.ok:
            tt=warp_detection(test,r,treatment);t1=time.perf_counter()
            dr=detect(rr,tt,r.valid_mask,treatment);dettime=time.perf_counter()-t1
            candidates=dr.candidates
            invalid_pixels=int(((dr.candidate_mask>0)&(r.valid_mask==0)).sum())
        row=dict(board=d['board'],profile=d['profile'],treatment=treatment,gt=d['gt'],
                 registration_quality=r.quality,registration_ok=r.ok,registration_metrics=r.metrics,
                 registration_s=regtime,detection_s=dettime,candidates=candidates,
                 invalid_mask_pixels_after_morphology=invalid_pixels)
        if r.warp is not None:
            points=np.array([[40.,40.],[860.,40.],[40.,560.],[860.,560.],[450.,300.]],np.float32)
            capture=cv2.transform(points[None],d['pose'])
            reconstructed=cv2.transform(capture,r.warp)[0]
            row['pose_error_px']=float(np.linalg.norm(points-reconstructed,axis=1).mean())
        for thresh in [.15,.3,.5]:row[f'candidate_iou_{thresh}']=matching(d['gt'],candidates,thresh)
        row['legacy_candidate_score']=score_variant(d['gt'],candidates)
        fixed=fixed_verdict(candidates,r.quality)
        row['fixed_verdicts']=dict(Counter(c['status'] for c in fixed))
        row['fixed_reported']=matching(d['gt'],[c for c in fixed if c['status'] in ['CONFIRMED_DEFECT','LIKELY_DEFECT']],.15)
        if with_agent and treatment in with_agent and r.ok:
            vs=vm=None
            if d['view'] is not None:
                if treatment=='legacy':vr=reg.register(rr,preprocess(d['view'],for_registration=False))
                else:vr=REG_FIXED.register(ref,d['view'])
                if vr.ok:vs=warp_detection(d['view'],vr,treatment);vm=vr.valid_mask
            ctx=rt.ToolContext(rr,tt,tt,r.valid_mask,cv2.absdiff(rr,tt),1-det.local_ncc(rr,tt),d['view'],vs,vm)
            t1=time.perf_counter();ac,n,errors=adaptive(candidates,ctx,r.quality,d['view'] is not None)
            row['agent_s']=time.perf_counter()-t1;row['tool_calls']=n;row['tool_errors']=errors
            row['agent_candidates']=ac;row['agent_verdicts']=dict(Counter(c['status'] for c in ac))
            row['agent_reported']=matching(d['gt'],[c for c in ac if c['status'] in ['CONFIRMED_DEFECT','LIKELY_DEFECT']],.15)
        row['post_registration_s']=time.perf_counter()-t0
        rows.append(row)
    return rows

def aggregate(rows,score='candidate_iou_0.15'):
    vals=[r[score] for r in rows if score in r];tp=sum(x['tp'] for x in vals);fp=sum(x['fp'] for x in vals);fn=sum(x['fn'] for x in vals)
    clean=[r for r in rows if r['profile']=='clean']
    return dict(n=len(vals),tp=tp,fp=fp,fn=fn,micro_precision=tp/(tp+fp) if tp+fp else 1.,
                micro_recall=tp/(tp+fn) if tp+fn else 1.,micro_f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.,
                macro_f1=float(np.mean([v['f1'] for v in vals])) if vals else None,
                clean_false_candidates=sum(len(r['candidates']) for r in clean),
                clean_boards=len(clean),registration_refusals=sum(not r['registration_ok'] for r in rows),
                mean_detection_s=float(np.mean([r['detection_s'] for r in rows])) if rows else None)

def summary(rows):
    result={}
    for treatment in sorted(set(r['treatment'] for r in rows)):
        tr=[r for r in rows if r['treatment']==treatment]
        item={s:aggregate(tr,s) for s in ['candidate_iou_0.15','candidate_iou_0.3','candidate_iou_0.5','fixed_reported']}
        item['per_profile']={p:aggregate([r for r in tr if r['profile']==p]) for p in PROFILES}
        item['per_type']={}
        item['size_bins']={}
        for kind in TYPES:
            n=hit=0
            for r in tr:
                for i,g in enumerate(r['gt']):
                    if g['type']==kind:n+=1;hit+=i in r['candidate_iou_0.15']['matched_gt']
            item['per_type'][kind]=dict(total=n,localized=hit,recall=hit/n if n else None)
        for name,lo,hi in [('small',0,256),('medium',256,1024),('large',1024,1e12)]:
            n=hit=0
            for r in tr:
                for i,g in enumerate(r['gt']):
                    if lo<=g['bbox'][2]*g['bbox'][3]<hi:n+=1;hit+=i in r['candidate_iou_0.15']['matched_gt']
            item['size_bins'][name]=dict(total=n,localized=hit,recall=hit/n if n else None)
        ar=[r for r in tr if 'agent_reported' in r]
        if ar:
            item['agent_reported']=aggregate(ar,'agent_reported')
            item['agent_verdicts']=dict(sum((Counter(r['agent_verdicts']) for r in ar),Counter()))
            item['mean_tool_calls']=float(np.mean([r['tool_calls'] for r in ar]))
        result[treatment]=item
    return result

def uncertainty(rows):
    boards=sorted(set(r['board'] for r in rows));rng=np.random.default_rng(260026)
    out={};base=[r for r in rows if r['treatment']=='legacy']
    for treatment in sorted(set(r['treatment'] for r in rows)):
        if treatment=='legacy':continue
        tr=[r for r in rows if r['treatment']==treatment];delta=[]
        for _ in range(2000):
            sample=rng.choice(boards,len(boards),replace=True)
            a=[r for b in sample for r in tr if r['board']==b]
            b=[r for b in sample for r in base if r['board']==b]
            delta.append(aggregate(a)['micro_f1']-aggregate(b)['micro_f1'])
        out[treatment]=dict(reference='legacy',metric='candidate micro-F1 at IoU .15',
                            board_clusters=len(boards),resamples=2000,delta_95_percentile_interval=np.percentile(delta,[2.5,97.5]).tolist(),
                            caveat='Few procedural board groups; repeated captures are not independent production samples.')
    return out

def probes():
    rng=np.random.default_rng(8)
    ref=cv2.GaussianBlur(rng.integers(15,240,(240,320),dtype=np.uint8),(7,7),0)
    cv2.putText(ref,'PCB 26',(35,125),cv2.FONT_HERSHEY_SIMPLEX,1.5,230,3)
    m=np.array([[1,0,3.],[0,1,-2.]],np.float32);test=cv2.warpAffine(ref,m,(320,240))
    er=reg._ecc_attempt(ref,test,None);fixed=REG_FIXED._ecc_attempt(ref,test,None)
    interior=np.zeros_like(ref);interior[15:-15,15:-15]=255
    mae=lambda a:float(np.abs(ref.astype(float)-a.astype(float))[interior>0].mean())
    ecc=dict(known_reference_to_test=m.tolist(),legacy_metrics=er.metrics,fixed_metrics=fixed.metrics,
             unaligned_mae=mae(test),legacy_aligned_mae=mae(er.warped_test),fixed_aligned_mae=mae(fixed.warped_test))
    test_def=ref.copy();cv2.circle(test_def,(150,120),9,20,-1)
    ctx=rt.ToolContext(ref,test_def,test_def,interior,cv2.absdiff(ref,test_def),1-det.local_ncc(ref,test_def))
    local=rt.tool_local_realignment(ctx,'probe',[138,108,24,24])
    # Diagnostic after-diff unit conversion only; transform-direction fix is separate.
    corrected_after_255=local.metrics['mean_diff_after']*255
    local_result=dict(metrics=local.metrics,supports_defect=local.supports_defect,
                      corrected_after_255_approx=corrected_after_255,
                      note='Stored after rounded to 2 decimals; approximate rescaling is diagnostic, not a corrected verifier.')
    gt=[dict(bbox=[0,0,10,10]),dict(bbox=[6,0,10,10])];cs=[dict(bbox=[0,0,10,10]),dict(bbox=[2,0,10,10])]
    mask=np.ones((100,100),np.uint8)*255;mask[45:55,45:55]=0
    kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(31,31))
    result=dict(environment=env(),ecc=ecc,local_realignment=local_result,
                matching=dict(legacy=score_variant(gt,cs),one_to_one=matching(gt,cs,.15)),
                validity_mask=dict(initial_invalid=int((mask==0).sum()),after_current_dilate=int((cv2.dilate(mask,kernel)==0).sum()),after_erode=int((cv2.erode(mask,kernel)==0).sum())),
                opencv_features={name:hasattr(cv2,name) for name in ['findTransformECC','findTransformECCWithMask','findTransformECCMultiScale','USAC_MAGSAC','SIFT_create','estimateAffinePartial2D']})
    # Prove deterministic repeated RANSAC is not four diverse hypotheses.
    src=rng.uniform(0,200,(60,1,2)).astype(np.float32);dst=cv2.transform(src,m);dst[::5]+=40
    warps=[cv2.estimateAffinePartial2D(src,dst,method=cv2.RANSAC,maxIters=5000,confidence=.999)[0].tolist() for _ in range(4)]
    result['ransac_repetition']=dict(unique_matrices=len({json.dumps(w) for w in warps}),matrices=warps)
    # Annotation audit uses identical observation conditions; never enters inference.
    coverage=[]
    for seed in range(600001,600005):
        b=Board(seed);clean,_=b.render(illum_strength=0,noise_sigma=0,illum_seed=1,noise_seed=2)
        for kind in TYPES:
            broken,ann=b.render(defects=[dict(kind=kind,seed=seed*31)],illum_strength=0,noise_sigma=0,illum_seed=1,noise_seed=2)
            changed=np.max(cv2.absdiff(clean,broken),axis=2)>4
            x,y,w,h=ann[0].to_json()['bbox'];inside=np.zeros_like(changed);inside[max(0,y):y+h,max(0,x):x+w]=True
            n=int(changed.sum());outside=int((changed&~inside).sum())
            coverage.append(dict(board=seed,type=kind,bbox=[x,y,w,h],changed_pixels=n,outside_bbox=outside,
                                 changed_fraction_outside=outside/n if n else None))
    result['annotation_coverage']=coverage
    dump('probes.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='annotation_coverage'},indent=2))
    print('Annotation audit:',sum(x['outside_bbox']>0 for x in coverage),'of',len(coverage),'boxes miss changed pixels')

def run(split):
    start=time.perf_counter()
    if split=='tune':seeds=range(200001,200005);treatments=TREATMENTS;agents=[]
    else:
        choice=json.loads((OUT/'selection.json').read_text())
        seeds=range(300001,300009);treatments=TREATMENTS;agents=['legacy','symmetric_ecc',choice['selected']]
    rows=[]
    for seed in seeds:
        for profile in PROFILES:
            d=scene(seed,profile);save_scene(d,split)
            rows.extend(evaluate_scene(d,treatments,agents))
            dump(f'{split}-rows.json',rows)
            print(split,seed,profile,'done',round(time.perf_counter()-start,1),'s',flush=True)
    sums=summary(rows);dump(f'{split}-summary.json',sums)
    if split=='tune':
        base=sums['symmetric_ecc']['candidate_iou_0.15']
        eligible=[t for t in TREATMENTS[3:] if sums[t]['candidate_iou_0.15']['clean_false_candidates']<=base['clean_false_candidates']
                  and sums[t]['candidate_iou_0.15']['micro_recall']>=base['micro_recall']]
        selected=max(['symmetric_ecc']+eligible,key=lambda t:sums[t]['candidate_iou_0.15']['micro_f1'])
        dump('selection.json',dict(selected=selected,eligible=eligible,criterion='tuning candidate micro F1 .15; no clean-FP or recall regression',
                                   locked_before_test=True,test_seed_range=[300001,300008]))
    else:dump('test-board-bootstrap.json',uncertainty(rows))
    # Separate wrong-board controls: abstention has no GT-defect recall score.
    wrong=[]
    for seed in list(seeds)[:2]:
        a=gray(Board(seed).render(illum_seed=seed,noise_seed=seed+1)[0])
        b=gray(Board(seed+900000).render(illum_seed=seed+2,noise_seed=seed+3)[0])
        for name,method in [('legacy',reg),('symmetric_ecc',REG_FIXED)]:
            r=method.register(a,b);wrong.append(dict(board=seed,treatment=name,ok=r.ok,metrics=r.metrics))
    dump(f'{split}-wrong-board.json',wrong)
    original=json.loads((ROOT/'evaluation/results.json').read_text())
    dump('original-baseline-snapshot.json',dict(sha256=hashlib.sha256((ROOT/'evaluation/results.json').read_bytes()).hexdigest(),overall=original['overall'],iou=original['iou_threshold']))
    dump(f'{split}-environment.json',dict(**env(),elapsed_s=time.perf_counter()-start,treatments=treatments,
                                        board_seeds=list(seeds),profiles=PROFILES,agent_treatments=agents))
    print(json.dumps({t:s['candidate_iou_0.15'] for t,s in sums.items()},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['probes','tune','test'],required=True)
    args=parser.parse_args()
    if args.phase=='probes':probes()
    else:run(args.phase)
