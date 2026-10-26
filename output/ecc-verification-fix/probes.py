"""Small, reproducible pre-fix/current correctness comparison."""
from pathlib import Path
import importlib.util
import json
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/tests')]
import cv2
import numpy as np
from app.cv import registration, region_tools, verification
from test_alignment_evidence import texture, context, candidate, evidence
OUT = Path(__file__).resolve().parent

def frozen(name):
    spec = importlib.util.spec_from_file_location(f'app.cv.probe_old_{name}',OUT/'baseline/backend/app/cv'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module

ref=texture();defect=ref.copy();cv2.circle(defect,(150,120),9,20,-1)
shifted=cv2.warpAffine(ref,np.float32([[1,0,3],[0,1,-2]]),(320,240))
ev=[evidence('local_realignment',False), evidence('independent_view',True)]
results={}
for label,reg,rt,ver in [('before',frozen('registration'),frozen('region_tools'),frozen('verification')),
                        ('after',registration,region_tools,verification)]:
    local=rt.tool_local_realignment(context(ref,defect),'R01',[138,108,24,24])
    result=reg._ecc_attempt(ref,shifted,None)
    interior=np.s_[20:-20,20:-20]
    results[label]=dict(local_injected_defect=dict(supports_defect=local.supports_defect,metrics=local.metrics),
                        conflicting_evidence_verdict=ver.verify_candidate(candidate(),ev,'good')[0],
                        global_ecc_interior_mae=float(np.abs(ref[interior].astype(float)-result.warped_test[interior]).mean()))
assert results['after']['local_injected_defect']['supports_defect'] is not False
assert results['after']['conflicting_evidence_verdict']=='NEEDS_REVIEW'
(OUT/'correctness-probes.json').write_text(json.dumps(results,indent=2,allow_nan=False))
print(json.dumps(results,indent=2))
