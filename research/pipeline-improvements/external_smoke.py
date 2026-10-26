"""Six traceable DeepPCB test pairs: compatibility smoke, not a new benchmark.

DeepPCB uses real scan backgrounds plus added artificial defects and prealigned,
binarized patches. Its README restricts data to research despite repo MIT license.
"""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
import cv2
import numpy as np
import experiments as e

COMMIT='08e98c4db5922613fb97176eb3d6497d48260cb1'
def download():
    tree=json.loads((e.HERE/'deeppcb-tree.json').read_text());files={x['path']:x for x in tree['tree']}
    first={}
    for line in (e.HERE/'deeppcb-test.txt').read_text().splitlines():first.setdefault(line.split('/')[0],line)
    groups=['group00041','group13000','group20085','group50600','group77000','group92000']
    manifest=[]
    for group in groups:
        image,anno=first[group].split();base=image.removesuffix('.jpg')
        for path in [f'PCBData/{base}_temp.jpg',f'PCBData/{base}_test.jpg',f'PCBData/{anno}']:
            url=f'https://raw.githubusercontent.com/tangsanli5201/DeepPCB/{COMMIT}/{path}'
            with urllib.request.urlopen(url,timeout=25) as response:content=response.read()
            gitsha=hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()
            assert gitsha==files[path]['sha'], 'Git blob hash mismatch'
            dest=e.HERE/'data'/'deeppcb'/Path(path).name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
            manifest.append(dict(group=group,path=path,url=url,git_blob_sha1=gitsha,
                                 sha256=hashlib.sha256(content).hexdigest(),bytes=len(content),local=str(dest.relative_to(e.HERE))))
    e.dump('deeppcb-download-manifest.json',dict(commit=COMMIT,selection='first listed test pair for six named groups; no score-based selection',
           data_terms='Research only per original README; repository code MIT does not override dataset restriction',files=manifest))
    print('Downloaded and hash-verified',len(manifest),'files')

def evaluate():
    manifest=json.loads((e.OUT/'deeppcb-download-manifest.json').read_text());rows=[]
    for group in sorted({x['group'] for x in manifest['files']}):
        fs=[x for x in manifest['files'] if x['group']==group]
        get=lambda ending:next(e.HERE/x['local'] for x in fs if x['local'].endswith(ending))
        ref=cv2.imread(str(get('_temp.jpg')),cv2.IMREAD_GRAYSCALE);test=cv2.imread(str(get('_test.jpg')),cv2.IMREAD_GRAYSCALE)
        gt=[]
        for line in get('.txt').read_text().splitlines():
            x1,y1,x2,y2,kind=map(int,line.split());gt.append(dict(bbox=[x1,y1,x2-x1,y2-y1],type=kind))
        pair=[]
        for name,module in [('legacy',e.reg),('symmetric_ecc',e.REG_FIXED),('erode_valid',e.REG_FIXED)]:
            r=module.register(ref,test);candidates=[]
            if r.ok:
                rr=e.reference_detection(ref,name);tt=e.warp_detection(test,r,name)
                d=e.detect(rr,tt,r.valid_mask,name);candidates=d.candidates
            pair.append(dict(treatment=name,ok=r.ok,registration=r.metrics,candidates=candidates,score=e.matching(gt,candidates,.15)))
        # Independent data-format diagnostic using supplied alignment, never
        # substitute GT masks for detector validity.
        provided_alignment=e.det.detect_candidates(ref,test,np.ones_like(ref)*255)
        binary_change=((ref>127)!=(test>127)).astype(np.uint8)*255
        n,lab,stats,cents=cv2.connectedComponentsWithStats(binary_change)
        binary_candidates=[dict(bbox=[int(x),int(y),int(w),int(h)]) for x,y,w,h,area in stats[1:] if area>=4]
        rows.append(dict(group=group,gt=gt,shape=list(ref.shape),test_rail_fraction=float(((test<=5)|(test>=250)).mean()),
                         production_variants=pair,provided_alignment_candidates=len(provided_alignment.candidates),
                         supplied_alignment_binary_xor_diagnostic=e.matching(gt,binary_candidates,.15),
                         diagnostic_note='XOR uses supplied prealignment and fixed binary threshold; no agent, class prediction, quality gate or capture robustness. Not a promoted pipeline.'))
    e.dump('deeppcb-smoke.json',dict(commit=COMMIT,pairs=6,rows=rows,
      caveat='Small purposive compatibility smoke. Mixed real scan/artificial-defect dataset; no production accuracy claim.'))
    for r in rows:print(r['group'],'rail',round(r['test_rail_fraction'],3),'GT',len(r['gt']),
      'candidate counts',[(v['treatment'],len(v['candidates'])) for v in r['production_variants']],
      'prealigned_raw',r['provided_alignment_candidates'],'xor',r['supplied_alignment_binary_xor_diagnostic']['tp'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--download',action='store_true');args=p.parse_args()
    if args.download:download()
    evaluate()
