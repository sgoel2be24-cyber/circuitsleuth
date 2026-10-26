import { useCallback, useEffect, useRef, useState } from 'react'
import type { Candidate, Verdict } from '../types'
import { VERDICT_STYLE } from './verdictStyles'

interface Props {
  inspectionId: string
  images: Record<string, string>
  candidates: Record<string, Candidate>
  selectedId: string | null
  onSelect: (id: string | null) => void
  diffHeatmapUrl: string | null
}
type Role = 'reference' | 'test' | 'aligned_test' | 'view2'
const ROLES: { key: Role; label: string }[] = [{key:'aligned_test',label:'Aligned test'},{key:'reference',label:'Reference'},{key:'test',label:'Original test'},{key:'view2',label:'View 2'}]
const loadImage = (src: string) => new Promise<HTMLImageElement>((resolve, reject) => { const im = new Image(); im.onload = () => resolve(im); im.onerror = reject; im.src = src })

export function BoardViewer({ inspectionId, images, candidates, selectedId, onSelect, diffHeatmapUrl }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [role, setRole] = useState<Role>(images.aligned_test ? 'aligned_test' : 'test')
  const [showBoxes, setShowBoxes] = useState(true)
  const [showHeatmap, setShowHeatmap] = useState(false)
  const [compare, setCompare] = useState(false)
  const [split, setSplit] = useState(50)
  const [view, setView] = useState({ scale: 1, ox: 0, oy: 0 })
  const [dimensions, setDimensions] = useState<[number,number] | null>(null)
  const [imageVersion, setImageVersion] = useState(0)
  const [imageError, setImageError] = useState(false)
  const [loading, setLoading] = useState(true)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const heatRef = useRef<HTMLImageElement | null>(null)
  const referenceRef = useRef<HTMLImageElement | null>(null)
  const dragRef = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null)
  const autoAligned = useRef(Boolean(images.aligned_test))
  const [hoverId, setHoverId] = useState<string | null>(null)
  const aligned = role === 'reference' || role === 'aligned_test'
  const roles = ROLES.filter(r => images[r.key])
  useEffect(() => { if (images.aligned_test && !autoAligned.current) { setRole('aligned_test'); autoAligned.current = true } }, [images.aligned_test])
  const fit = useCallback((img = imgRef.current) => {
    const wrap = wrapRef.current
    if (!wrap || !img) return
    const scale = Math.min(wrap.clientWidth / img.width, wrap.clientHeight / img.height) * .9
    setView({scale,ox:(wrap.clientWidth-img.width*scale)/2,oy:(wrap.clientHeight-img.height*scale)/2})
  }, [])
  const zoom = useCallback((factor: number, point?: {x:number;y:number}) => {
    const wrap = wrapRef.current
    if (!wrap) return
    const mx = point?.x ?? wrap.clientWidth/2, my = point?.y ?? wrap.clientHeight/2
    setView(v => { const scale = Math.max(.05,Math.min(20,v.scale*factor)); const k = scale/v.scale; return {scale,ox:mx-(mx-v.ox)*k,oy:my-(my-v.oy)*k} })
  }, [])
  useEffect(() => {
    let cancelled = false
    imgRef.current = null
    loadImage(`/api/inspections/${inspectionId}/images/${role}`).then(im => {
      if (cancelled) return
      imgRef.current = im; setDimensions([im.width,im.height]); fit(im); setImageVersion(v=>v+1); setLoading(false)
    }).catch(() => { if (!cancelled) { setImageError(true); setLoading(false) } })
    return () => { cancelled = true }
  }, [inspectionId,role,fit])
  useEffect(() => {
    let cancelled = false
    heatRef.current = null
    if (diffHeatmapUrl) loadImage(diffHeatmapUrl).then(im => { if (!cancelled) { heatRef.current=im; setImageVersion(v=>v+1) } }).catch(()=>{})
    return () => { cancelled = true }
  }, [diffHeatmapUrl])
  useEffect(() => {
    let cancelled = false
    referenceRef.current = null
    loadImage(`/api/inspections/${inspectionId}/images/reference`).then(im => { if (!cancelled) {referenceRef.current=im;setImageVersion(v=>v+1)} }).catch(()=>{})
    return () => { cancelled = true }
  }, [inspectionId])
  const draw = useCallback(() => {
    const canvas=canvasRef.current, img=imgRef.current, wrap=wrapRef.current
    if (!canvas || !wrap) return
    const dpr=window.devicePixelRatio || 1
    canvas.width=wrap.clientWidth*dpr;canvas.height=wrap.clientHeight*dpr
    const ctx=canvas.getContext('2d');if(!ctx)return
    ctx.setTransform(dpr,0,0,dpr,0,0)
    ctx.clearRect(0,0,wrap.clientWidth,wrap.clientHeight)
    if (!img) return
    const {scale,ox,oy}=view
    ctx.imageSmoothingEnabled=scale<3
    ctx.drawImage(img,ox,oy,img.width*scale,img.height*scale)
    if(compare && role==='aligned_test' && referenceRef.current) {
      const boundary=ox+img.width*scale*split/100
      ctx.save();ctx.beginPath();ctx.rect(ox,oy,img.width*scale*split/100,img.height*scale);ctx.clip();ctx.drawImage(referenceRef.current,ox,oy,img.width*scale,img.height*scale);ctx.restore()
      ctx.strokeStyle='#d4f7e9';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(boundary,oy);ctx.lineTo(boundary,oy+img.height*scale);ctx.stroke()
    }
    if(showHeatmap && aligned && heatRef.current) {ctx.globalAlpha=.5;ctx.drawImage(heatRef.current,ox,oy,img.width*scale,img.height*scale);ctx.globalAlpha=1}
    if(!showBoxes || !aligned)return
    const colors:Record<string,string>={'text-red-300':'#f87171','text-amber-300':'#fbbf24','text-emerald-300':'#8be9be','text-violet-300':'#bca4fa','text-slate-400':'#94a3b8','text-cyan-300':'#67e8f9'}
    for(const c of Object.values(candidates)) {
      const [x,y,w,h]=c.bbox, selected=c.region_id===selectedId, hovered=c.region_id===hoverId
      const color=colors[(VERDICT_STYLE[c.status as Verdict]??VERDICT_STYLE.SUSPECTED).color]??'#67e8f9'
      const px=ox+x*scale,py=oy+y*scale,pw=w*scale,ph=h*scale
      ctx.lineWidth=selected?2.5:hovered?2:1;ctx.strokeStyle=color;ctx.fillStyle=color+(selected?'24':'0b');ctx.fillRect(px-4,py-4,pw+8,ph+8);ctx.setLineDash(selected?[]:[4,3]);ctx.strokeRect(px-4,py-4,pw+8,ph+8);ctx.setLineDash([])
      ctx.font='500 10px ui-monospace, monospace';const tw=ctx.measureText(c.region_id).width
      ctx.fillStyle='#0c171feb';ctx.fillRect(px-4,py-23,tw+14,17);ctx.strokeRect(px-4,py-23,tw+14,17);ctx.fillStyle=color;ctx.fillText(c.region_id,px+3,py-11)
    }
  },[view,showBoxes,showHeatmap,compare,split,role,aligned,candidates,selectedId,hoverId])
  useEffect(()=>{draw()},[draw,imageVersion])
  useEffect(()=>{const wrap=wrapRef.current;if(!wrap)return;const observer=new ResizeObserver(()=>fit());observer.observe(wrap);return()=>observer.disconnect()},[fit])
  useEffect(()=>{
    const wrap=wrapRef.current;if(!wrap)return
    const wheel=(e:WheelEvent)=>{e.preventDefault();const rect=wrap.getBoundingClientRect();zoom(e.deltaY<0?1.12:1/1.12,{x:e.clientX-rect.left,y:e.clientY-rect.top})}
    wrap.addEventListener('wheel',wheel,{passive:false});return()=>wrap.removeEventListener('wheel',wheel)
  },[zoom])
  const hitTest=(cx:number,cy:number)=>{
    if(!aligned || !showBoxes)return null
    const rect=canvasRef.current!.getBoundingClientRect(),x=(cx-rect.left-view.ox)/view.scale,y=(cy-rect.top-view.oy)/view.scale
    return Object.values(candidates).find(c=>{const[bx,by,bw,bh]=c.bbox;return x>=bx-4&&x<=bx+bw+4&&y>=by-4&&y<=by+bh+4})?.region_id??null
  }
  return <div className="panel flex h-full min-h-0 flex-col overflow-hidden">
    <div className="flex flex-wrap items-center gap-2 border-b border-[#25333f] px-3 py-2.5"><div className="flex flex-wrap gap-1" aria-label="Image selection">{roles.map(r=><button key={r.key} aria-pressed={role===r.key} onClick={()=>{if(role!==r.key){setLoading(true);setImageError(false);setRole(r.key)}}} className={`rounded px-2.5 py-1.5 text-[11px] ${role===r.key?'bg-cyan-300/12 text-cyan-200':'text-slate-400 hover:bg-white/5'}`}>{r.label}</button>)}</div><span className="ml-auto flex gap-1"><button className="viewer-button" aria-label="Zoom out" onClick={()=>zoom(1/1.25)}>−</button><button className="viewer-button mono" onClick={()=>fit()} title="Fit image (F)">Fit</button><button className="viewer-button" aria-label="Zoom in" onClick={()=>zoom(1.25)}>+</button></span></div>
    <div className="flex flex-wrap items-center gap-4 border-b border-[#25333f] px-3 py-2 text-[10px] text-slate-400"><label className="flex items-center gap-1.5"><input type="checkbox" disabled={!aligned} checked={showBoxes&&aligned} onChange={e=>setShowBoxes(e.target.checked)} className="accent-cyan-300"/>Regions</label><label className="flex items-center gap-1.5"><input type="checkbox" disabled={!diffHeatmapUrl||!aligned} checked={showHeatmap&&aligned} onChange={e=>setShowHeatmap(e.target.checked)} className="accent-cyan-300"/>Difference map</label><label className="flex items-center gap-1.5"><input type="checkbox" disabled={role!=='aligned_test'} checked={compare&&role==='aligned_test'} onChange={e=>setCompare(e.target.checked)} className="accent-cyan-300"/>Compare</label>{compare&&role==='aligned_test'&&<input aria-label="Reference comparison split" type="range" min="0" max="100" value={split} onChange={e=>setSplit(Number(e.target.value))} className="w-24 accent-emerald-300"/>}<span className="mono ml-auto text-[8px]">{aligned?'REFERENCE COORDINATES':'ORIGINAL CAPTURE · OVERLAYS HIDDEN'}</span></div>
    <div ref={wrapRef} className="viewer-surface relative min-h-0 flex-1 cursor-crosshair" tabIndex={0} role="group" aria-label="Board viewer. Plus or minus to zoom, F to fit, arrow keys to pan. Select candidates using region buttons below."
      onKeyDown={e=>{if(['+','=','-','f','F','Home','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))e.preventDefault();if(e.key==='+'||e.key==='=')zoom(1.25);if(e.key==='-')zoom(1/1.25);if(['f','F','Home'].includes(e.key))fit();if(e.key.startsWith('Arrow'))setView(v=>({...v,ox:v.ox+(e.key==='ArrowLeft'?30:e.key==='ArrowRight'?-30:0),oy:v.oy+(e.key==='ArrowUp'?30:e.key==='ArrowDown'?-30:0)}))}}
      onPointerDown={e=>{const hit=hitTest(e.clientX,e.clientY);if(hit){onSelect(hit);return}dragRef.current={x:e.clientX,y:e.clientY,ox:view.ox,oy:view.oy};e.currentTarget.setPointerCapture(e.pointerId)}}
      onPointerMove={e=>{const d=dragRef.current;if(d)setView(v=>({...v,ox:d.ox+e.clientX-d.x,oy:d.oy+e.clientY-d.y}));else setHoverId(hitTest(e.clientX,e.clientY))}}
      onPointerUp={()=>{dragRef.current=null}} onPointerCancel={()=>{dragRef.current=null}} onLostPointerCapture={()=>{dragRef.current=null}}>
      <canvas ref={canvasRef} className="h-full w-full" role="img" aria-label={`${ROLES.find(r=>r.key===role)?.label} PCB image; ${Object.keys(candidates).length} candidate regions`}/>
      {loading&&<div className="absolute inset-0 grid place-items-center bg-[#0b131b]/80 text-xs text-slate-400">Loading image…</div>}
      {imageError&&<div role="alert" className="absolute inset-0 grid place-items-center bg-[#0b131b]/90 p-8 text-center text-xs text-red-200">Image unavailable. Select another view or reload the inspection.</div>}
    </div>
    <div className="viewer-bottom"><span className="h-1.5 w-1.5 rounded-full bg-emerald-300"/>{dimensions?`${dimensions[0]} × ${dimensions[1]} px`:'IMAGE'}<span>{Math.round(view.scale*100)}%</span><span className="ml-auto">{compare&&role==='aligned_test'?'REFERENCE ← | → ALIGNED TEST':'SCROLL TO ZOOM · DRAG TO PAN'}</span></div>
  </div>
}


