"""Post-tuning diagnostics on NEW identities, not a tuning pass on test outcomes.

Outputs explain failure stages and check the memory-only policy harness against
the real persistent orchestrator using storage isolated under this research dir.
"""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import cv2
import experiments as e
from app import store
from app.config import settings
from app.agent.orchestrator import run_inspection
from app.tools import registry
from evaluation.benchmark import make_state

def tiny():
    instrument=e.fork_module(e.det,'app.cv.research_detection_diagnostic',[
        ('    num, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)',
         '''    globals()['_stages'] = dict(diff=diff.copy(), threshold=diff_t, mismatch=mismatch.copy(),
           base=base_mask.copy(), added=added_mask.copy(), observation=obs_valid.copy(),
           post=mask.copy(), structureless=structureless.copy())
    num, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)''')])
    rows=[]
    for seed in range(400001,400005):
        board=e.Board(seed)
        ref,_=board.render(illum_seed=seed+1,noise_seed=seed+2)
        for kind in e.TYPES:
            test,ann=board.render(defects=[dict(kind=kind,seed=seed*31)],illum_seed=seed+3,noise_seed=seed+4)
            rr=e.preprocess(e.gray(ref),for_registration=False)
            tt=e.preprocess(e.gray(test),for_registration=False)
            result=instrument.detect_candidates(rr,tt,np.ones_like(rr)*255)
            stages=instrument._stages;x,y,w,h=ann[0].to_json()['bbox']
            crop=lambda a:a[y:y+h,x:x+w]
            row=dict(board=seed,type=kind,bbox=[x,y,w,h],matched=e.matching([ann[0].to_json()],result.candidates,.15)['tp'],
                     diff_threshold=float(stages['threshold']),max_diff=float(crop(stages['diff']).max()),
                     pixels_over_threshold=int((crop(stages['diff'])>=stages['threshold']).sum()),
                     structural_gate_pixels=int((crop(stages['mismatch'])>=.25).sum()),
                     structureless_pixels=int(crop(stages['structureless']).sum()),
                     base_pixels=int((crop(stages['base'])>0).sum()),added_pixels=int((crop(stages['added'])>0).sum()),
                     post_morph_pixels=int((crop(stages['post'])>0).sum()),candidates=result.candidates)
            rows.append(row)
    e.dump('diagnostic-defect-stages.json',rows)
    print('pinhole stage diagnostics',json.dumps([r for r in rows if r['type']=='pinhole'],indent=2))

def parity():
    settings.data_dir=e.HERE/'orchestrator-parity-store'
    rows=json.loads((e.OUT/'test-rows.json').read_text())
    results=[]
    for profile in ['mild','gain','glare']:
        seed=300001;row=next(r for r in rows if r['board']==seed and r['profile']==profile and r['treatment']=='legacy')
        folder=e.HERE/'data'/'test'/f'b{seed}_{profile}'
        images=dict(reference=str(folder/'ref.png'),test=str(folder/'test.png'),
                    view2=str(folder/'view.png') if (folder/'view.png').exists() else None)
        state=make_state(images,'research_parity',seed,12);state['id']=f'research_parity_{profile}'
        # No inspection index row is needed; run_inspection persists state/events
        # and artifacts exclusively beneath settings.data_dir.
        # Parity is with the historical study, not today's production fixes.
        with patch.multiple(registry, reg_mod=e.reg, rt=e.rt, ver_mod=e.ver):
            actual=asyncio.run(run_inspection(state))
        projection=lambda cs:[dict(bbox=c['bbox'],status=c['status'],tools_used=c['tools_used']) for c in cs]
        expected=projection(row['agent_candidates']);observed=projection(list(actual['candidates'].values()))
        results.append(dict(profile=profile,expected=expected,actual=observed,
                            harness_calls=row['tool_calls'],actual_calls=actual['tool_calls_used'],
                            equal=expected==observed and row['tool_calls']==actual['tool_calls_used'],
                            stop_reason=actual['stop_reason']))
    e.dump('orchestrator-parity.json',results)
    assert all(x['equal'] for x in results), 'Policy harness mismatch: inspect before interpreting agent metrics'
    print('Real-orchestrator parity:',len(results),'cases pass')

def analysis():
    rows=json.loads((e.OUT/'test-rows.json').read_text());results={}
    # Fixed score thresholds are descriptive operating curves, not an optimized
    # deployment threshold. No data are fed back into the detector.
    for treatment in ['legacy','symmetric_ecc','multiplicative']:
        tr=[r for r in rows if r['treatment']==treatment];curve=[]
        for threshold in [0,.01,.02,.04,.08,.12,.2]:
            scored=[]
            for r in tr:
                c=[c for c in r['candidates'] if c['difference_score']*c['structural_mismatch_score']>=threshold]
                scored.append(dict(r,score=e.matching(r['gt'],c,.15)))
            curve.append(dict(threshold=threshold,**e.aggregate(scored,'score')))
        ar=[r for r in tr if 'agent_candidates' in r]
        automatic=[r for r in ar if not any(c['status'] in ['NEEDS_REVIEW','NOT_EVALUABLE'] for c in r['agent_candidates'])]
        wrong=sum(bool(r['gt'])!=any(c['status'] in ['CONFIRMED_DEFECT','LIKELY_DEFECT'] for c in r['agent_candidates']) for r in automatic)
        counts=sum((e.Counter(r['agent_verdicts']) for r in ar),e.Counter())
        pose=[r for r in tr if r['profile']=='pose']
        results[treatment]=dict(score_curve=curve,automatic_boards=len(automatic),total_boards=len(tr),
          automatic_board_coverage=len(automatic)/len(tr),automatic_board_errors=wrong,
          selective_board_risk=wrong/len(automatic) if automatic else None,
          candidate_review_fraction=sum(counts[k] for k in ['NEEDS_REVIEW','NOT_EVALUABLE'])/max(sum(counts.values()),1),
          mean_tool_calls=float(np.mean([r['tool_calls'] for r in ar])),
          mean_pose_error_px=float(np.mean([r['pose_error_px'] for r in pose])),
          p95_pose_error_px=float(np.percentile([r['pose_error_px'] for r in pose],95)),
          detection_latency_p50_s=float(np.median([r['detection_s'] for r in tr])),
          detection_latency_p95_s=float(np.percentile([r['detection_s'] for r in tr],95)),
          clean_reported_false_alarms=sum(r['agent_reported']['fp'] for r in ar if r['profile']=='clean'),
          candidate_fp=sum(r['candidate_iou_0.15']['fp'] for r in tr),
          invalid_mask_pixels=sum(r['invalid_mask_pixels_after_morphology'] for r in tr),
          missing_view_statuses=dict(sum((e.Counter(r['agent_verdicts']) for r in ar if r['profile']=='gain'),e.Counter())))
    # Pinholes can be completely absent from candidates, so selective risk on
    # decided candidates alone would conceal detector misses.
    e.dump('operating-points.json',results)
    print('Operating points:',json.dumps({k:{kk:vv for kk,vv in v.items() if kk!='score_curve'} for k,v in results.items()},indent=2))

if __name__=='__main__':
    tiny();parity();analysis()
