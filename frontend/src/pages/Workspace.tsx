import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, streamEvents } from '../api'
import type { Inspection, InspectionEvent, Verdict } from '../types'
import { BoardViewer } from '../components/BoardViewer'
import { AgentFeed } from '../components/AgentFeed'
import { RegionDetail } from '../components/RegionDetail'
import { StatusDot, VerdictChip } from '../components/ui'
import { ReportView } from './Report'
import { Link } from 'react-router-dom'
import { Icon } from '../components/Icon'

export function Workspace({ publicDemo = false }: { publicDemo?: boolean }) {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const [ins, setIns] = useState<Inspection | null>(null)
  const [events, setEvents] = useState<InspectionEvent[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [tab, setTab] = useState<'activity' | 'region' | 'report'>('activity')
  const [error, setError] = useState<string | null>(null)
  const [rerunning, setRerunning] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const startedRef = useRef<string | null>(null)
  const runStatus = ins?.status

  useEffect(() => {
    let active = true
    // Completed runs may open after the last SSE event, or through a proxy
    // without SSE. Load persisted history on entry and status transitions.
    api.getEvents(id).then(next => {
      if (!active) return
      setEvents(prev => {
        const merged = new Map(prev.map(ev => [ev.seq, ev]))
        next.forEach(ev => merged.set(ev.seq, ev))
        return [...merged.values()].sort((a, b) => a.seq - b.seq)
      })
    })
    return () => { active = false }
  }, [id, runStatus])

  const refresh = useCallback(() => {
    api.getInspection(id).then((d) => { setIns(d); setError(null) }).catch((e) => setError(e.message))
  }, [id])

  const startInspection = useCallback(async () => {
    if (startedRef.current === id) return
    startedRef.current = id
    setStarting(true)
    setStartError(null)
    try {
      await api.start(id)
      refresh()
    } catch (e) {
      startedRef.current = null
      setStartError(e instanceof Error ? e.message : String(e))
      // A lost response may still have started the server-side task.
      refresh()
    } finally {
      setStarting(false)
    }
  }, [id, refresh])

  useEffect(() => {
    api.getInspection(id).then((d) => {
      setIns(d)
      if (d.status === 'created' && d.execution_mode !== 'mcp') {
        void startInspection()
      }
    }).catch((e) => setError(e.message))
  }, [id, startInspection])

  useEffect(() => {
    const es = streamEvents(
      id,
      (ev) => {
        setEvents((prev) => (prev.some((p) => p.seq === ev.seq) ? prev : [...prev, ev]))
        if (['detection_completed', 'candidate_verified', 'tool_executed', 'report_ready',
             'inspection_completed', 'inspection_failed', 'inspection_aborted',
             'registration_completed', 'registration_failed'].includes(ev.type)) {
          refresh()
        }
      },
      () => refresh(),
    )
    return () => es.close()
  }, [id, refresh])

  useEffect(() => {
    if (!runStatus || !['created', 'running'].includes(runStatus)) return
    const timer = setInterval(() => {
      refresh()
      api.getEvents(id).then((next) => setEvents(prev => {
        const merged = new Map(prev.map(ev => [ev.seq, ev]))
        next.forEach(ev => merged.set(ev.seq, ev))
        return [...merged.values()].sort((a, b) => a.seq - b.seq)
      }))
    }, 2500)
    return () => clearInterval(timer)
  }, [id, runStatus, refresh])

  if (error && !ins) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <div role="alert" className="panel border-red-400/30 p-4 text-sm text-red-300">{error}<button className="ml-4 underline" onClick={refresh}>Retry</button><Link className="ml-4 underline" to="/">Overview</Link></div>
      </div>
    )
  }
  if (!ins) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="mono text-xs text-slate-600">loading run<span className="caret">▍</span></p>
      </div>
    )
  }

  const running = ins.status === 'running'
  const selectedCandidate = selected ? ins.candidates[selected] : null
  const heatUrl = ins.detection?.artifacts?.diff_heatmap
    ? api.artifactUrl(id, ins.detection.artifacts.diff_heatmap)
    : null
  const counts = countVerdicts(ins)
  const phase = events.at(-1)?.phase ?? 'OBSERVE'
  const phases = ['OBSERVE', 'ALIGN', 'DETECT', 'PLAN', 'ACT', 'VERIFY', 'DECIDE']
  const phaseIndex = Math.max(0, phases.indexOf(phase))
  const decided = Object.values(ins.candidates).filter(c => c.status !== 'SUSPECTED').length

  const submitReview = async (regionId: string, decision: 'confirmed' | 'rejected', note: string) => {
    await api.submitReview(id, regionId, decision, note)
    refresh()
    api.getEvents(id).then(setEvents)
  }

  const rerunInspection = async (file?: File) => {
    setRerunning(true)
    setError(null)
    try {
      const r = await api.rerun(id, file)
      nav(`/inspections/${r.inspection_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setRerunning(false)
    }
  }

  return (
    <div className="workspace-layout mx-auto max-w-[1800px]">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div><Link to="/" className="text-[10px] text-slate-400 hover:text-cyan-200">← Inspection ledger</Link><h1 className="mt-1 text-xl font-medium tracking-tight text-slate-100">Inspection workspace</h1></div>
        <div className="flex items-center gap-3"><span className="mono text-[10px] text-slate-400">{['synthetic_demo', 'demo'].includes(ins.summary?.source ?? '') ? 'SYNTHETIC DEMONSTRATION' : ins.summary?.source?.toUpperCase()}</span>{running && <button disabled={stopping} onClick={async () => { setStopping(true); try { await api.abort(id); refresh() } catch (e) { setError(e instanceof Error ? e.message : String(e)) } finally { setStopping(false) } }} className="rounded border border-red-300/30 bg-red-400/5 px-3 py-2 text-[11px] text-red-200">{stopping ? 'Stopping…' : 'Stop inspection'}</button>}{!running && <button disabled={rerunning} onClick={() => void rerunInspection()} className="viewer-button disabled:opacity-50">{rerunning ? 'Re-running…' : 'Re-run inspection'}</button>}<button onClick={() => setTab('report')} className="viewer-button flex items-center gap-2"><Icon name="download" size={14}/>Report</button></div>
      </div>
      {error && <div role="alert" className="error-banner"><span>{error}</span><button onClick={refresh}>Retry</button></div>}
      {ins.status === 'created' && ins.execution_mode !== 'mcp' && <div role={startError ? 'alert' : 'status'} className="error-banner"><span>{starting ? 'Starting inspection…' : startError ?? 'Inspection has not started.'}</span><button disabled={starting} onClick={() => void startInspection()}>{starting ? 'Starting…' : 'Retry Start'}</button></div>}
      {ins.status === 'created' && ins.execution_mode === 'mcp' && <div role="status" className="panel mb-3 p-3 text-sm text-slate-300">This inspection is being driven by an external MCP client. Continue that session or create a fresh re-run.</div>}
      {/* ------------------------------------------------------- header strip */}
      <div className="ticked panel mb-3 flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2.5">
        <div className="flex items-center gap-2.5">
          <StatusDot status={ins.status} />
          <span className="mono text-[13px] text-slate-100">{id}</span>
          {ins.summary?.scenario_id && (
            <span className="mono rounded bg-white/5 px-1.5 py-0.5 text-[9px] text-slate-400">
              {ins.summary.scenario_id}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {Object.entries(counts).map(([k, n]) =>
            n > 0 ? <span key={k} className="flex items-center gap-1"><span className="mono text-[10px] text-slate-400">{n}</span><VerdictChip status={k as Verdict} small /></span> : null,
          )}
          {Object.keys(ins.candidates).length === 0 && ins.status === 'completed' && ins.stop_reason === 'no_candidates' && ins.registration?.quality !== 'failed' && (
            <span className="mono rounded bg-emerald-400/10 px-2 py-0.5 text-[10px] text-emerald-300 ring-1 ring-emerald-400/40">
              board clean — no anomalies
            </span>
          )}
          {ins.stop_reason === 'registration_failed' && <VerdictChip status="NOT_EVALUABLE" small />}
        </div>
        <div className="mono ml-auto flex flex-wrap items-center gap-x-4 gap-y-1 text-[10.5px] text-slate-400">
          {ins.registration && (
            <span>
              align{' '}
              <span className={
                ins.registration.quality === 'good' ? 'text-emerald-300'
                  : ins.registration.quality === 'marginal' ? 'text-amber-300' : 'text-red-300'
              }>
                {ins.registration.quality}
              </span>
              {ins.registration.inliers != null && (
                <span className="text-slate-600"> · {ins.registration.inliers} inl · {ins.registration.mean_residual_px}px</span>
              )}
            </span>
          )}
          <span>
            tools <span className="text-cyan-300">{ins.tool_calls_used}</span>
            <span className="text-slate-600">/{ins.config.max_tool_calls}</span>
          </span>
          <span>iter <span className="text-slate-200">{ins.iterations}</span></span>
          {ins.summary?.duration_s != null && ins.summary.duration_s > 0 && (
            <span className="text-slate-200">{ins.summary.duration_s.toFixed(2)}s</span>
          )}
          {ins.stop_reason && (
            <span className="rounded bg-white/5 px-1.5 py-0.5 text-slate-400">{ins.stop_reason}</span>
          )}
        </div>
      </div>

      {/* missing-view operator loop */}
      {!publicDemo && !ins.images.view2 && ins.status === 'completed' && ins.review_requests.some(r => !r.resolved) && (
        <div className="ticked panel mb-3 flex flex-wrap items-center gap-3 border-violet-400/25 px-4 py-2.5">
          <span className="label-eyebrow text-violet-300/90">operator loop open</span>
          <span className="text-[12px] text-slate-400">
            This run had no secondary capture, so ambiguous regions could only be escalated.
            Add a new capture of the same board and the agent re-inspects with real optical evidence.
          </span>
          <ViewUpload onFile={rerunInspection} busy={rerunning} />
        </div>
      )}

      <div className="phase-rail" aria-label={`Inspection phase: ${phase}`}>{phases.map((p, i) => <span key={p} className={i === phaseIndex && running ? 'current' : events.some(ev => ev.phase === p) ? 'done' : ''}><i>{events.some(ev => ev.phase === p) && !running ? '✓' : i + 1}</i>{p}</span>)}<span className="mono ml-auto pl-3 text-[9px]">{decided}/{Object.keys(ins.candidates).length} REGIONS DECIDED</span></div>

      {/* ------------------------------------------------------- main grid */}
      <div className="workspace-grid">
        <div className="workspace-board-column grid min-h-0 grid-rows-[1fr_auto] gap-3">
          <BoardViewer
            inspectionId={id}
            images={ins.images}
            candidates={ins.candidates}
            selectedId={selected}
            onSelect={(rid) => { setSelected(rid); if (rid) setTab('region') }}
            diffHeatmapUrl={heatUrl}
          />
          <div className="ticked panel flex items-center gap-2 overflow-x-auto px-3 py-2">
            {Object.keys(ins.candidates).length === 0 ? (
              <span className="text-xs text-slate-500">
                {running ? 'detection pending…' : 'no candidate regions'}
              </span>
            ) : (
              Object.values(ins.candidates).map((c) => (
                <button
                  key={c.region_id}
                  onClick={() => { setSelected(c.region_id); setTab('region') }}
                  className={`flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-[11px] ring-1 transition ${
                    selected === c.region_id
                      ? 'bg-[#16233a] ring-cyan-400/60'
                      : 'ring-[#1d2a3d] hover:bg-[#121c2a]'
                  }`}
                >
                  <span className="mono text-slate-300">{c.region_id}</span>
                  <VerdictChip status={c.status} small />
                </button>
              ))
            )}
          </div>
        </div>

        <div className="workspace-evidence ticked panel flex min-h-0 flex-col overflow-hidden">
          <div className="flex border-b border-[#1d2a3d]">
            {([['activity', 'Agent'], ['region', 'Region'], ['report', 'Report']] as const).map(
              ([k, label]) => (
                <button
                  key={k}
                  aria-pressed={tab === k}
                  onClick={() => setTab(k)}
                  className={`relative px-4 py-2.5 text-xs font-medium transition-colors ${
                    tab === k ? 'text-cyan-200' : 'text-slate-500 hover:text-slate-200'
                  }`}
                >
                  {label}
                  {k === 'region' && selectedCandidate && (
                    <span className="mono ml-1 text-[9px] text-slate-500">{selectedCandidate.region_id}</span>
                  )}
                  {tab === k && (
                    <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-t bg-cyan-400" />
                  )}
                </button>
              ),
            )}
          </div>
          <div className="min-h-0 flex-1">
            {tab === 'activity' && (
              <AgentFeed events={events} running={running} artifactUrl={(n) => api.artifactUrl(id, n)} />
            )}
            {tab === 'region' && (selectedCandidate ? (
              <RegionDetail
                key={selectedCandidate.region_id}
                candidate={selectedCandidate} inspectionId={id}
                reviewDisabled={ins.status !== 'completed'}
                onSubmitReview={submitReview}
                artifactUrl={(n) => api.artifactUrl(id, n)}
              />
            ) : (
              <p className="p-6 text-center text-xs text-slate-500">
                Select a region on the board or from the strip below.
              </p>
            ))}
            {tab === 'report' && <ReportView inspectionId={id} ins={ins} />}
          </div>
        </div>
      </div>
    </div>
  )
}

function ViewUpload({ onFile, busy }: { onFile: (f: File) => void; busy: boolean }) {
  const ref = useRef<HTMLInputElement>(null)
  return (
    <>
      <input
        ref={ref}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) onFile(f)
        }}
      />
      <button
        disabled={busy}
        onClick={() => ref.current?.click()}
        className="mono shrink-0 rounded-md bg-violet-400/15 px-3 py-1.5 text-[11px] font-medium text-violet-200 ring-1 ring-violet-400/40 transition hover:bg-violet-400/25 disabled:opacity-50"
      >
        {busy ? 're-running…' : 'add capture & re-run →'}
      </button>
    </>
  )
}

function countVerdicts(ins: Inspection): Record<string, number> {
  const out: Record<string, number> = {}
  for (const c of Object.values(ins.candidates)) out[c.status] = (out[c.status] ?? 0) + 1
  return out
}

