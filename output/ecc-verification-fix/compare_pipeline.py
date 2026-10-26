"""Before/after actual orchestrator comparison; does not edit research outputs."""
from __future__ import annotations
import asyncio
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT)]
import cv2
import numpy as np
from app.config import settings
from app.tools import registry
from app.agent.orchestrator import run_inspection
from app.cv import registration, region_tools, verification
from evaluation.benchmark import make_state, score_variant
from tools.generate_dataset import Board

OUT = Path(__file__).resolve().parent
cv2.setNumThreads(1)
cv2.setRNGSeed(260026)


def load_baseline(name):
    path = OUT / 'baseline/backend/app/cv' / f'{name}.py'
    spec = importlib.util.spec_from_file_location(f'app.cv.pre_fix_{name}', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


old_reg = load_baseline('registration')
old_tools = load_baseline('region_tools')
old_tools.register = old_reg.register
old_ver = load_baseline('verification')
methods = {'before': (old_reg, old_tools, old_ver), 'after': (registration, region_tools, verification)}
rows = []
with tempfile.TemporaryDirectory(prefix='circuitsleuth-ecc-compare-') as temporary:
    settings.data_dir = Path(temporary)
    folders = sorted((ROOT / 'research/pipeline-improvements/data/test').glob('b*'))
    assert len(folders) == 48
    for name, modules in methods.items():
        registry.reg_mod, registry.rt, registry.ver_mod = modules
        for folder in folders:
            meta = json.loads((folder / 'annotations.json').read_text())
            images = dict(reference=str(folder / 'ref.png'), test=str(folder / 'test.png'),
                          view2=str(folder / 'view.png') if (folder / 'view.png').exists() else None)
            state = make_state(images, 'ecc_comparison', meta['board'], 12)
            state['id'] = f"compare_{name}_{folder.name}"
            result = asyncio.run(run_inspection(state))
            assert result['status'] == 'completed', result.get('stop_reason')
            candidates = list(result['candidates'].values())
            rows.append(dict(treatment=name,board=meta['board'],profile=meta['profile'],
                             score=score_variant(meta['gt'], candidates, verdict_level=True),
                             candidate_score=score_variant(meta['gt'], candidates),
                             verdicts=dict(Counter(c['status'] for c in candidates)),
                             tool_calls=result['tool_calls_used'],stop_reason=result['stop_reason'],
                             candidates=[dict(region_id=c['region_id'],bbox=c['bbox'],status=c['status'],
                                              tools=c['tools_used']) for c in candidates]))
        print(name, '48 actual orchestrator inspections completed', flush=True)
    registry.reg_mod, registry.rt, registry.ver_mod = methods['after']

controls = []
gray = lambda image: cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
for seed in [200001,200002,300001,300002]:
    ref = gray(Board(seed).render(illum_seed=seed,noise_seed=seed+1)[0])
    wrong = gray(Board(seed+900000).render(illum_seed=seed+2,noise_seed=seed+3)[0])
    for name, (reg, _, _) in methods.items():
        result = reg.register(ref,wrong)
        controls.append(dict(board=seed,treatment=name,control='wrong_board',accepted=result.ok,
                             quality=result.quality))
for seed in range(700001,700005):
    board = Board(seed)
    ref = gray(board.render(illum_seed=seed+11,noise_seed=seed+12)[0])
    test = gray(board.render(illum_seed=seed+21,noise_seed=seed+22)[0])
    pose = cv2.getRotationMatrix2D((450,300),1.25,1.005).astype(np.float32)
    pose[:,2] += [4,-3]
    shifted = cv2.warpAffine(test,pose,(900,600))
    points = np.float32([[[40,40],[860,40],[40,560],[860,560],[450,300]]])
    for name, (reg, _, _) in methods.items():
        result = reg.register(ref,shifted)
        error = float(np.linalg.norm(cv2.transform(cv2.transform(points,pose),result.warp)-points,axis=2).mean()) if result.ok else None
        controls.append(dict(board=seed,treatment=name,control='fresh_pose',accepted=result.ok,
                             mean_anchor_error_px=error))

summary = {}
for name in methods:
    selected = [r for r in rows if r['treatment']==name]
    def scores(key):
        tp,fp,fn = [sum(r[key][k] for r in selected) for k in ['tp','fp','fn']]
        return dict(tp=tp,fp=fp,fn=fn,micro_precision=tp/max(tp+fp,1),micro_recall=tp/max(tp+fn,1),
                    micro_f1=2*tp/max(2*tp+fp+fn,1))
    counts = sum((Counter(r['verdicts']) for r in selected), Counter())
    summary[name] = dict(reported=scores('score'),candidates=scores('candidate_score'),verdicts=dict(counts),
                         mean_tool_calls=sum(r['tool_calls'] for r in selected)/len(selected),
                         clean_false_positives=sum(r['score']['fp'] for r in selected if r['profile']=='clean'))
no_new_wrong_accepts = all(not r['accepted'] or next(b for b in controls if b['board']==r['board'] and b['treatment']=='before' and b['control']=='wrong_board')['accepted'] for r in controls if r['treatment']=='after' and r['control']=='wrong_board')
output = dict(summary=summary,controls=controls,rows=rows,no_new_wrong_board_accepts=no_new_wrong_accepts,
              caveats=['48 repeated captures from eight synthetic board identities; diagnostic regression set, not a new untouched test set.',
                       'Scoring uses preserved legacy matcher at IoU 0.15 for before/after comparability.',
                       'Four fresh pose identities assess transform error; no thresholds tuned on these results.'])
(OUT/'comparison.json').write_text(json.dumps(output,indent=2,allow_nan=False))
print(json.dumps(dict(summary=summary,no_new_wrong_board_accepts=no_new_wrong_accepts),indent=2))
assert no_new_wrong_accepts, 'New wrong-board false acceptance'
