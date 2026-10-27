import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { InspectionEvent, Scenario, Summary, Verdict } from '../types'
import { StatusDot, VerdictChip } from '../components/ui'
import { Icon } from '../components/Icon'

export function Dashboard() {
  const [inspections, setInspections] = useState<Summary[]>([])
  const [sys, setSys] = useState<Record<string, unknown> | null>(null)
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [events, setEvents] = useState<InspectionEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [visibleCount, setVisibleCount] = useState(9)
  const load = useCallback(async () => {
    try { const rows = await api.listInspections(); setInspections(rows); setError(null) }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => {
    api.listInspections().then(rows => { setInspections(rows); setError(null) }).catch(e => setError(e.message)).finally(() => setLoading(false))
    api.systemInfo().then(setSys).catch(() => {})
    api.scenarios().then(setScenarios).catch(() => {})
    const timer = setInterval(load, 10000)
    return () => clearInterval(timer)
  }, [load])
  const latest = inspections.find(i => i.status === 'completed')
  const latestId = latest?.id
  useEffect(() => {
    let active = true
    if (latestId) api.getEvents(latestId).then(e => { if (active) setEvents(e.slice(-5).reverse()) })
    return () => { active = false }
  }, [latestId])
  const stats = useMemo(() => {
    const done = inspections.filter(i => i.status === 'completed')
    const sum = (key: 'confirmed' | 'likely' | 'cleared' | 'needs_review' | 'not_evaluable') => inspections.reduce((n, i) => n + (i[key] ?? 0), 0)
    const durations = done.map(i => i.duration_s ?? 0).filter(d => d > 0)
    return { done: done.length, confirmed: sum('confirmed'), likely: sum('likely'), cleared: sum('cleared'), review: sum('needs_review'), notEval: sum('not_evaluable'), avg: durations.length ? durations.reduce((a,b) => a+b,0)/durations.length : null }
  }, [inspections])
  const distribution = [
    { label: 'Confirmed', count: stats.confirmed, color: '#fb8888' },
    { label: 'Likely', count: stats.likely, color: '#f8c76c' },
    { label: 'Cleared', count: stats.cleared, color: '#8be9be' },
    { label: 'Review', count: stats.review, color: '#bca4fa' },
    { label: 'Not evaluable', count: stats.notEval, color: '#8899a8' },
  ]
  const total = distribution.reduce((n, d) => n+d.count, 0)
  const filtered = inspections.filter(i => `${i.id} ${i.scenario_id ?? 'custom upload'} ${i.status}`.toLowerCase().includes(query.toLowerCase()) && (filter === 'all' || (filter === 'review' ? i.needs_review > 0 : i.status === filter)))
  const preview = latest ? api.imageUrl(latest.id, 'test') : scenarios[0] ? api.scenarioImage(scenarios[0].id) : null
  return (
    <div className="page-container dashboard-page">
      <div className="page-heading rise"><div><div className="label-eyebrow flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-cyan-300"/> INSPECTION COMMAND CENTER</div><h1>See the board.<br className="mobile-break"/> <span className="text-slate-400">Know the evidence.</span></h1><p>A clearer view of every inspection, every decision, every detail.</p></div><Link to="/new" className="primary-button"><Icon name="plus" size={17}/>New inspection</Link></div>
      {error && <div role="alert" className="error-banner"><span>Could not connect to the inspection engine: {error}</span><button onClick={load}>Retry connection →</button></div>}
      <div className="overview-hero rise rise-1">
        <div className="hero-copy"><div className="label-eyebrow">ACTIVE PERCEPTION · PCB INSPECTION</div><h2>Beyond detection.<br/><span>Decisions with proof.</span></h2><p>OpenCV finds what changed. The agent chooses where to look next. Every finding gets a second look before a final decision.</p><Link to={latest ? `/inspections/${latest.id}` : '/new'} className="hero-link">{latest ? 'Explore latest inspection' : 'Launch your first inspection'}<Icon name="arrow" size={19}/></Link><div className="hero-capabilities"><span><Icon name="scan" size={14}/>Adaptive inspection</span><span><Icon name="shield" size={14}/>Evidence-backed verdicts</span></div></div>
        <div className="hero-visual">{preview ? <img src={preview} alt={latest ? 'Actual test image from latest completed inspection' : 'Bundled synthetic PCB test image'}/> : <div className="preview-empty">Board preview appears when the engine is available.</div>}<div className="visual-vignette"/><div className="visual-topline"><span className="mono">{latest ? 'LATEST INSPECTION' : 'SCENARIO PREVIEW'}</span><span className="visual-pill">{latest?.source === 'upload' ? 'UPLOADED IMAGE' : latest ? latest.source.toUpperCase() : 'SYNTHETIC'}</span></div><div className="reticle reticle-tl"/><div className="reticle reticle-br"/><div className="visual-caption"><div className="mono">{latest?.id ?? 'REFERENCE-BASED SURFACE INSPECTION'}</div><span>{latest ? `${latest.candidate_count} regions assessed · ${latest.tool_calls_used} follow-up calls` : 'Reproducible, seeded demonstration imagery'}</span>{latest && <Link to={`/inspections/${latest.id}`} aria-label="Open latest inspection"><Icon name="arrow"/></Link>}</div></div>
      </div>
      <div className="metric-grid rise rise-2">
        <Metric label="Total inspections" value={loading ? '…' : inspections.length} detail={`${stats.done} completed inspections`} icon="layers"/>
        <Metric label="Confirmed defects" value={loading ? '…' : stats.confirmed} detail={`${stats.likely} additional likely defects`} icon="scan" tone="red"/>
        <Metric label="Average cycle time" value={stats.avg === null ? '—' : stats.avg.toFixed(2)} suffix={stats.avg === null ? '' : 's'} detail="Measured across completed runs" icon="clock"/>
        <Metric label="Awaiting review" value={loading ? '…' : stats.review} detail="Regions requiring an operator" icon="shield" tone="violet"/>
      </div>
      <div className="dashboard-lower rise rise-3">
        <section className="panel ledger-panel">
          <div className="section-heading"><div><h2>Inspection ledger</h2><p>Your recorded runs, ready to investigate.</p></div><span className="record-count mono">{inspections.length} RECORDS</span></div>
          <div className="ledger-controls"><div className="filter-tabs" aria-label="Filter inspections">{[['all','All runs'],['completed','Completed'],['review','Needs review']].map(([key,label]) => <button key={key} aria-pressed={filter === key} onClick={() => { setFilter(key); setVisibleCount(9) }} className={filter === key ? 'selected' : ''}>{label}</button>)}</div><label className="ledger-search"><Icon name="search" size={15}/><input value={query} onChange={e => { setQuery(e.target.value); setVisibleCount(9) }} placeholder="Search inspections…" aria-label="Search inspections"/></label></div>
          <div className="ledger-table-wrap"><table className="ledger-table"><thead><tr><th>INSPECTION / SOURCE</th><th>STATUS</th><th>FINDINGS</th><th>CYCLE</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>
            {loading && [0,1,2].map(n => <tr key={n}><td colSpan={5}><div className="skeleton h-9"/></td></tr>)}
            {!loading && filtered.slice(0, visibleCount).map(i => <tr key={i.id}><td><Link to={`/inspections/${i.id}`} className="run-link"><span className="run-icon"><Icon name="chip" size={17}/></span><span><strong className="mono">{i.id}</strong><small>{i.scenario_id?.replaceAll('_',' ') ?? 'Custom upload'} <span>· {new Date(i.created_at).toLocaleDateString(undefined, {month:'short',day:'numeric'})}</span></small></span></Link></td><td><span className="run-status"><StatusDot status={i.status}/>{i.status}</span></td><td><Outcome inspection={i}/></td><td className="mono cycle-cell">{i.duration_s ? `${i.duration_s.toFixed(2)}s` : '—'}</td><td><Link className="open-run" to={`/inspections/${i.id}`} aria-label={`Open inspection ${i.id}`}><Icon name="arrow" size={16}/></Link></td></tr>)}
          </tbody></table></div>
          {!loading && filtered.length === 0 && <div className="ledger-empty"><Icon name={inspections.length ? 'search' : 'scan'} size={30}/><h3>{inspections.length ? 'No matching inspections' : 'Your first inspection starts here.'}</h3><p>{inspections.length ? 'Try another search or change the filter.' : 'Choose a synthetic scenario or bring your own board images.'}</p>{!inspections.length && <Link to="/new" className="hero-link">Start an inspection <Icon name="arrow" size={16}/></Link>}</div>}
          {filtered.length > 9 && <div className="ledger-footer"><span>Showing {Math.min(visibleCount, filtered.length)} of {filtered.length} runs</span>{visibleCount < filtered.length && <button onClick={() => setVisibleCount(n => n + 9)}>Show more inspections →</button>}</div>}
        </section>
        <aside className="dashboard-right">
          <section className="panel distribution-panel"><div className="section-heading"><h2>Region outcomes</h2><Icon name="activity" size={16}/></div><div className="outcome-total"><strong>{total}</strong><span>regions assessed</span></div><div className="distribution-track" role="img" aria-label={distribution.map(d => `${d.label}: ${d.count}`).join(', ')}>{distribution.map(d => d.count > 0 && <span key={d.label} style={{width:`${d.count / total * 100}%`, background:d.color}}/>)}</div><div className="distribution-legend">{distribution.map(d => <div key={d.label}><span className="legend-dot" style={{background:d.color}}/><span>{d.label}</span><strong className="mono">{d.count}</strong></div>)}</div></section>
          <section className="panel telemetry-panel"><div className="section-heading"><h2>Agent activity</h2><span className="mono text-[9px] text-slate-500">LAST RUN</span></div>{events.length ? <ol>{events.map(ev => <li key={ev.seq}><span className="event-node"/><div><span className="mono event-phase">{ev.phase}</span><p>{ev.message}</p></div></li>)}</ol> : <p className="p-5 text-xs text-slate-400">Actual tool activity appears after your first inspection.</p>}</section>
        </aside>
      </div>
      <footer className="runtime-footer"><span className="flex items-center gap-2"><Icon name="chip" size={15}/> RUNTIME <b>OpenCV {String(sys?.opencv_version ?? '—')}</b><span className="runtime-python">Python {String(sys?.python_version ?? '—')}</span></span><span>OpenCV processing in this runtime <span className="mx-2 text-slate-600">/</span><a className="underline" href="https://github.com/sgoel2be24-cyber/circuitsleuth/blob/main/docs/AWS_EXECUTION_2026-10-27.md" target="_blank" rel="noreferrer">Versioned AWS execution receipt ↗</a></span></footer>
    </div>
  )
}

function Metric({ label, value, suffix, detail, icon, tone = '' }: { label: string; value: number | string; suffix?: string; detail: string; icon: string; tone?: string }) {
  return <section className={`metric-card ${tone}`}><div className="metric-title">{label}<Icon name={icon} size={17}/></div><div className="metric-value">{value}<span>{suffix}</span></div><p>{detail}</p></section>
}
function Outcome({ inspection: i }: { inspection: Summary }) {
  if (i.not_evaluable > 0 || i.stop_reason === 'registration_failed') return <VerdictChip status="NOT_EVALUABLE" small/>
  const statuses: [Verdict, number][] = [['CONFIRMED_DEFECT', i.confirmed], ['LIKELY_DEFECT', i.likely ?? 0], ['NEEDS_REVIEW', i.needs_review]]
  const active = statuses.filter(([, n]) => n > 0)
  if (active.length) return <div className="flex flex-wrap gap-1.5">{active.slice(0,2).map(([s,n]) => <span key={s} className="flex items-center gap-1"><span className="mono text-[10px] text-slate-400">{n}</span><VerdictChip status={s} small/></span>)}</div>
  if (i.status === 'completed' && i.stop_reason === 'no_candidates') return <span className="text-xs text-emerald-300">No anomalies</span>
  if (i.cleared > 0) return <span className="text-xs text-emerald-300">{i.cleared} cleared</span>
  return <span className="text-xs text-slate-500">{i.status === 'running' ? 'Analysing…' : '—'}</span>
}
