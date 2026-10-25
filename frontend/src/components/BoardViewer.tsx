import { useCallback, useEffect, useRef, useState } from 'react'
import type { Candidate, Verdict } from '../types'
import { VERDICT_STYLE } from './ui'

interface Props {
  inspectionId: string
  images: Record<string, string>
  candidates: Record<string, Candidate>
  selectedId: string | null
  onSelect: (id: string | null) => void
  diffHeatmapUrl: string | null
}

type Role = 'reference' | 'test' | 'view2'

const ROLES: { key: Role; label: string }[] = [
  { key: 'reference', label: 'Reference' },
  { key: 'test', label: 'Test' },
  { key: 'view2', label: 'View 2' },
]

export function BoardViewer({ inspectionId, images, candidates, selectedId, onSelect, diffHeatmapUrl }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [role, setRole] = useState<Role>('test')
  const [showBoxes, setShowBoxes] = useState(true)
  const [showHeatmap, setShowHeatmap] = useState(false)
  const [view, setView] = useState({ scale: 1, ox: 0, oy: 0 })
  const imgRef = useRef<HTMLImageElement | null>(null)
  const heatRef = useRef<HTMLImageElement | null>(null)
  const dragRef = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null)
  const [hoverId, setHoverId] = useState<string | null>(null)

  const roles = ROLES.filter((r) => images[r.key])

  useEffect(() => { if (!roles.find((r) => r.key === role)) setRole(roles[0]?.key ?? 'test') /* eslint-disable-next-line */ }, [roles.length])

  const loadImage = (src: string) =>
    new Promise<HTMLImageElement>((resolve, reject) => {
      const im = new Image()
      im.onload = () => resolve(im)
      im.onerror = reject
      im.src = src
    })

  // fit on first load of an image
  const fit = useCallback((img: HTMLImageElement) => {
    const wrap = wrapRef.current
    if (!wrap) return
    const scale = Math.min(wrap.clientWidth / img.width, wrap.clientHeight / img.height) * 0.94
    setView({
      scale,
      ox: (wrap.clientWidth - img.width * scale) / 2,
      oy: (wrap.clientHeight - img.height * scale) / 2,
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    loadImage(apiImage(inspectionId, role)).then((im) => {
      if (cancelled) return
      imgRef.current = im
      fit(im)
      draw()
    }).catch(() => { /* image may not exist yet */ })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inspectionId, role])

  useEffect(() => {
    if (!showHeatmap || !diffHeatmapUrl) { heatRef.current = null; draw(); return }
    loadImage(diffHeatmapUrl).then((im) => { heatRef.current = im; draw() }).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showHeatmap, diffHeatmapUrl])

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    const img = imgRef.current
    if (!canvas || !img) return
    const wrap = wrapRef.current
    if (!wrap) return
    canvas.width = wrap.clientWidth * window.devicePixelRatio
    canvas.height = wrap.clientHeight * window.devicePixelRatio
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.fillStyle = '#0a0e13'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    const { scale, ox, oy } = view
    ctx.imageSmoothingEnabled = scale < 3
    ctx.drawImage(img, ox, oy, img.width * scale, img.height * scale)
    if (showHeatmap && heatRef.current) {
      ctx.globalAlpha = 0.55
      ctx.drawImage(heatRef.current, ox, oy, img.width * scale, img.height * scale)
      ctx.globalAlpha = 1
    }
    if (!showBoxes) return
    for (const c of Object.values(candidates)) {
      const [x, y, w, h] = c.bbox
      const st = VERDICT_STYLE[c.status as Verdict] ?? VERDICT_STYLE.SUSPECTED
      const colorVar: Record<string, string> = {
        'text-red-300': '#f87171',
        'text-amber-300': '#fbbf24',
        'text-emerald-300': '#34d399',
        'text-violet-300': '#a78bfa',
        'text-slate-400': '#94a3b8',
        'text-cyan-300': '#22d3ee',
      }
      const color = colorVar[st.color] ?? '#22d3ee'
      const px = ox + x * scale
      const py = oy + y * scale
      const pw = w * scale
      const ph = h * scale
      const selected = c.region_id === selectedId
      const hovered = c.region_id === hoverId
      ctx.lineWidth = selected ? 2.5 : hovered ? 2 : 1.25
      ctx.strokeStyle = color
      ctx.setLineDash(selected ? [] : [5, 3])
      ctx.strokeRect(px - 3, py - 3, pw + 6, ph + 6)
      ctx.setLineDash([])
      if (selected) {
        ctx.strokeStyle = color + '66'
        ctx.lineWidth = 8
        ctx.strokeRect(px - 3, py - 3, pw + 6, ph + 6)
      }
      // label
      const label = `${c.region_id}`
      ctx.font = '600 11px ui-monospace, monospace'
      const tw = ctx.measureText(label).width
      ctx.fillStyle = color + 'cc'
      ctx.fillRect(px - 3, py - 20, tw + 10, 15)
      ctx.fillStyle = '#0b0f14'
      ctx.fillText(label, px + 2, py - 9)
    }
  }, [candidates, view, showBoxes, showHeatmap, selectedId, hoverId])

  useEffect(() => { draw() }, [draw])
  useEffect(() => {
    const onResize = () => draw()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [draw])

  const toImageCoords = (cx: number, cy: number) => {
    const rect = canvasRef.current!.getBoundingClientRect()
    return { x: (cx - rect.left - view.ox) / view.scale, y: (cy - rect.top - view.oy) / view.scale }
  }

  const hitTest = (cx: number, cy: number): string | null => {
    const { x, y } = toImageCoords(cx, cy)
    for (const c of Object.values(candidates)) {
      const [bx, by, bw, bh] = c.bbox
      if (x >= bx - 4 && x <= bx + bw + 4 && y >= by - 4 && y <= by + bh + 4) return c.region_id
    }
    return null
  }

  return (
    <div className="panel flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#223047] px-3 py-2">
        <div className="flex overflow-hidden rounded-md ring-1 ring-[#223047]">
          {roles.map((r) => (
            <button
              key={r.key}
              onClick={() => setRole(r.key)}
              className={`px-3 py-1 text-xs font-medium transition-colors ${
                role === r.key ? 'bg-cyan-400/15 text-cyan-300' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
        <label className="ml-2 flex cursor-pointer items-center gap-1.5 text-xs text-slate-400">
          <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} className="accent-cyan-400" />
          Regions
        </label>
        <label className={`flex items-center gap-1.5 text-xs ${diffHeatmapUrl ? 'cursor-pointer text-slate-400' : 'text-slate-600'}`}>
          <input
            type="checkbox"
            disabled={!diffHeatmapUrl}
            checked={showHeatmap}
            onChange={(e) => setShowHeatmap(e.target.checked)}
            className="accent-cyan-400"
          />
          Diff heatmap
        </label>
        <span className="ml-auto font-mono text-[10px] text-slate-500">
          scroll: zoom · drag: pan · click: select
        </span>
      </div>
      <div
        ref={wrapRef}
        className="relative min-h-0 flex-1 cursor-crosshair"
        onWheel={(e) => {
          e.preventDefault()
          const rect = wrapRef.current!.getBoundingClientRect()
          const mx = e.clientX - rect.left
          const my = e.clientY - rect.top
          const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
          setView((v) => {
            const scale = Math.max(0.1, Math.min(14, v.scale * factor))
            const k = scale / v.scale
            return { scale, ox: mx - (mx - v.ox) * k, oy: my - (my - v.oy) * k }
          })
        }}
        onPointerDown={(e) => {
          const hit = hitTest(e.clientX, e.clientY)
          if (hit) { onSelect(hit); return }
          dragRef.current = { x: e.clientX, y: e.clientY, ox: view.ox, oy: view.oy }
          ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
        }}
        onPointerMove={(e) => {
          if (dragRef.current) {
            const d = dragRef.current
            setView((v) => ({ ...v, ox: d.ox + (e.clientX - d.x), oy: d.oy + (e.clientY - d.y) }))
          } else {
            setHoverId(hitTest(e.clientX, e.clientY))
          }
        }}
        onPointerUp={() => { dragRef.current = null }}
      >
        <canvas ref={canvasRef} className="h-full w-full" />
      </div>
    </div>
  )
}

function apiImage(id: string, role: Role) {
  return `/api/inspections/${id}/images/${role}`
}
