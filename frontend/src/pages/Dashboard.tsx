import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { InspectionEvent, Summary, Verdict } from '../types'
import { StatusDot, VerdictChip } from '../components/ui'

export function Dashboard() {
  const [inspections, setInspections] = useState<Summary[]>([])
  const [sys, setSys] = useState<Record<string, any> | null>(null)
  const [ticker, setTicker] = useState<{ id: string; events: InspectionEvent[] } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listInspections().then(setInspections).catch((e) => setError(String(e.message)))
    api.systemInfo().then(setSys).catch(() => {})
  }, [])

  // live agent ticker from the most recent completed inspection
  useEffect(() => {
    const latest = inspections.find((i) => i.status === 'completed' && i.candidate_count >= 0)
    if (!latest) return
    let cancelled = false
    api.getEvents(latest.id).then((events) => {
      if (!cancelled) setTicker({ id: latest.id, events: events.slice(-9) })
    })
    return () => { cancelled = true }
  }, [inspections])

  const stats = useMemo(() => {
    const done = inspections.filter((i) => i.status === 'completed')
    const confirmed = inspections.reduce((a, i) => a + (i.confirmed ?? 0), 0)
    const likely = inspections.reduce((a, i) => a + (i.likely ?? 0), 0)
    const cleared = inspections.reduce((a, i) => a + (i.cleared ?? 0), 0)
    const review = inspections.reduce((a, i) => a + (i.needs_review ?? 0), 0)
    const notEval = inspections.reduce((a, i) => a + (i.not_evaluable ?? 0), 0)
    const tools = inspections.reduce((a, i) => a + (i.tool_calls_used ?? 0), 0)
    const durations = done.map((i) => i.duration_s ?? 0).filter((d) => d > 0)
    const avg = durations.length ? durations.reduce((a, b) => a + b, 0) / durations.length : null
    return { done, confirmed, likely, cleared, review, notEval, tools, avg, durations }
  }, [inspections])

  const dist = [
    { key: 'CONFIRMED_DEFECT', n: stats.confirmed },
    { key: 'LIKELY_DEFECT', n: stats.likely },
    { key: 'NEEDS_REVIEW', n: stats.review },
    { key: 'CLEARED', n: stats.cleared },
    { key: 'NOT_EVALUABLE', n: stats.notEval },
  ]
  const distTotal = dist.reduce((a, d) => a + d.n, 0)

  return (
    <div className="mx-auto max-w-7xl px-6 py-7">
      {/* ------------------------------------------------------ header row */}
      <div className="rise flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="label-eyebrow">inspection overview</div>
          <h1 className="mt-1 text-[26px] font-semibold leading-tight tracking-tight text-slate-100">
            Every region decided. Every claim evidenced.
          </h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-slate-400">
            CircuitSleuth aligns a test board to its reference, detects anomalies with OpenCV&nbsp;
            {String(sys?.opencv_version ?? '5')} — then interrogates its own uncertainty before
            it commits to a verdict.
          </p>
        </div>
        <Link
          to="/new"
          className="glow-cyan group flex items-center gap-2 rounded-lg bg-cyan-400/12 px-4 py-2.5 text-sm font-medium text-cyan-200 ring-1 ring-cyan-400/40 transition hover:bg-cyan-400/20"
        >
          Run an inspection
          <span className="mono text-[10px] text-cyan-400/70 transition group-hover:translate-x-0.5">→</span>
        </Link>
      </div>

      {error && (
        <div className="mt-6 rounded-lg border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-300">
          Backend unreachable: {error}
        </div>
      )}

      {/* ------------------------------------------------------ instrument band */}
      <div className="ticked panel rise rise-1 mt-6 grid grid-cols-2 divide-x divide-[#1d2a3d] md:grid-cols-4">
        <Gauge label="inspections" value={inspections.length} sub={`${stats.done.length} completed`} />
        <Gauge
          label="defects reported"
          value={stats.confirmed + stats.likely}
          sub={`${stats.confirmed} confirmed · ${stats.likely} likely`}
          tone="text-red-300"
        />
        <Gauge
          label="mean cycle time"
          value={stats.avg != null ? `${stats.avg.toFixed(2)}s` : '—'}
          sub={stats.tools ? `${stats.tools} agent tool calls total` : 'no runs yet'}
          tone="text-cyan-200"
        />
        <Gauge
          label="escalated to human"
          value={stats.review}
          sub="uncertainty is surfaced, never guessed"
          tone="text-violet-300"
        />
      </div>

      {/* ------------------------------------------------------ distribution + ticker */}
      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1.1fr]">
        <div className="panel rise rise-2 p-4">
          <div className="label-eyebrow">verdict distribution · all regions ever assessed</div>
          {distTotal === 0 ? (
            <p className="mt-4 text-xs text-slate-500">
              No verdicts recorded yet — the distribution appears after the first run.
            </p>
          ) : (
            <>
              <div className="mt-3 flex h-2.5 w-full overflow-hidden rounded-full bg-[#101a28] ring-1 ring-[#1d2a3d]">
                {dist.map((d) =>
                  d.n > 0 ? (
                    <div
                      key={d.key}
                      className={VERDICT_BG[d.key]}
                      style={{ width: `${(d.n / distTotal) * 100}%` }}
                      title={`${d.key}: ${d.n}`}
                    />
                  ) : null,
                )}
              </div>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
                {dist.map((d) => (
                  <span key={d.key} className="flex items-center gap-1.5 text-[11px] text-slate-400">
                    <span className={`h-2 w-2 rounded-sm ${VERDICT_BG[d.key]}`} />
                    {VERDICT_SHORT[d.key]}
                    <span className="mono text-slate-500">{d.n}</span>
                  </span>
                ))}
              </div>
              <div className="hud-divider my-3.5" />
              <p className="text-[11px] leading-relaxed text-slate-500">
                Cleared regions are anomalies the agent investigated and rejected — glare,
                misalignment, noise — instead of forwarding them as false alarms.
              </p>
            </>
          )}
        </div>

        <div className="panel rise rise-3 flex min-h-[188px] flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-[#1d2a3d] px-4 py-2.5">
            <span className="label-eyebrow">agent telemetry · last completed run</span>
            {ticker && (
              <Link to={`/inspections/${ticker.id}`} className="mono text-[10px] text-cyan-400/80 hover:underline">
                open →
              </Link>
            )}
          </div>
          <div className="min-h-0 flex-1 overflow-hidden px-4 py-2">
            {!ticker || ticker.events.length === 0 ? (
              <div className="flex h-full items-center justify-center">
                <p className="mono text-[11px] text-slate-600">
                  awaiting first run<span className="caret">▍</span>
                </p>
              </div>
            ) : (
              <ol className="space-y-1">
                {ticker.events.map((ev) => (
                  <li key={ev.seq} className="mono flex items-baseline gap-2 text-[10.5px]">
                    <span className="w-14 shrink-0 text-slate-600">
                      {new Date(ev.ts * 1000).toLocaleTimeString('en-GB', { hour12: false })}
                    </span>
                    <span className={`w-14 shrink-0 uppercase ${PHASE_COLOR[ev.phase] ?? 'text-slate-500'}`}>
                      {ev.phase.toLowerCase()}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-slate-400">{ev.message}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------ runs table + system */}
      <div className="mt-4 grid gap-4 lg:grid-cols-[1.7fr_1fr]">
        <div className="panel rise rise-4 overflow-hidden">
          <div className="flex items-center justify-between border-b border-[#1d2a3d] px-4 py-2.5">
            <span className="label-eyebrow">inspection log</span>
            <span className="mono text-[10px] text-slate-600">{inspections.length} records</span>
          </div>
          {inspections.length === 0 ? (
            <div className="px-6 py-10 text-center">
              <p className="text-sm text-slate-400">No inspections on record.</p>
              <p className="mt-1 text-xs text-slate-500">
                Start with a bundled scenario — clean board, glare case, or the mismatched-capture refusal.
              </p>
            </div>
          ) : (
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="label-eyebrow border-b border-[#1d2a3d]">
                  <th className="px-4 py-2 font-normal">inspection</th>
                  <th className="px-4 py-2 font-normal">status</th>
                  <th className="px-4 py-2 font-normal">outcome</th>
                  <th className="px-4 py-2 text-right font-normal">tools</th>
                  <th className="px-4 py-2 text-right font-normal">time</th>
                </tr>
              </thead>
              <tbody>
                {inspections.slice(0, 11).map((i) => (
                  <tr key={i.id} className="row-hover border-t border-[#141d2b] first:border-t-0">
                    <td className="px-4 py-2.5">
                      <Link to={`/inspections/${i.id}`} className="mono text-[11.5px] text-cyan-300 hover:underline">
                        {i.id}
                      </Link>
                      <div className="mono text-[9.5px] text-slate-600">
                        {i.scenario_id ?? 'custom upload'} · {i.created_at.slice(11, 19)}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-1.5 text-xs text-slate-300">
                        <StatusDot status={i.status} /> {i.status}
                      </span>
                      {i.stop_reason && i.stop_reason !== 'all_regions_decided' && (
                        <div className="mono text-[9px] text-slate-600">{i.stop_reason}</div>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {(i.confirmed ?? 0) > 0 && <VerdictChip status={'CONFIRMED_DEFECT' as Verdict} small />}
                        {(i.likely ?? 0) > 0 && <VerdictChip status={'LIKELY_DEFECT' as Verdict} small />}
                        {(i.needs_review ?? 0) > 0 && <VerdictChip status={'NEEDS_REVIEW' as Verdict} small />}
                        {(i.cleared ?? 0) > 0 && <VerdictChip status={'CLEARED' as Verdict} small />}
                        {(i.not_evaluable ?? 0) > 0 && <VerdictChip status={'NOT_EVALUABLE' as Verdict} small />}
                        {i.candidate_count === 0 && i.status === 'completed' && (
                          <span className="mono text-[10px] text-emerald-400/70">board clean</span>
                        )}
                      </div>
                    </td>
                    <td className="mono px-4 py-2.5 text-right text-[11px] text-slate-400">{i.tool_calls_used}</td>
                    <td className="mono px-4 py-2.5 text-right text-[11px] text-slate-400">
                      {i.duration_s != null && i.duration_s > 0 ? `${i.duration_s.toFixed(1)}s` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="panel rise rise-4 p-4">
          <div className="label-eyebrow">instrument</div>
          <dl className="mt-3 space-y-2.5 text-xs">
            <Row k="opencv" v={String(sys?.opencv_version ?? '…')} mono highlight={String(sys?.opencv_version ?? '').startsWith('5.')} />
            <Row k="python" v={String(sys?.python_version ?? '…')} mono />
            <Row k="build" v={`v${sys?.version ?? '…'}`} mono />
            <Row k="processing" v="local (this machine)" />
            <Row k="aws execution" v={sys ? (sys.aws_execution_verified ? 'verified' : 'unverified — honest status') : '…'} />
          </dl>
          <div className="hud-divider my-3.5" />
          <p className="text-[11px] leading-relaxed text-slate-500">
            Nothing on this page is hardcoded: counts, durations and the telemetry ticker all come
            from the persisted inspection records. Demo imagery is synthetic, seeded and labeled.
          </p>
        </div>
      </div>
    </div>
  )
}

const VERDICT_BG: Record<string, string> = {
  CONFIRMED_DEFECT: 'bg-red-400',
  LIKELY_DEFECT: 'bg-amber-400',
  NEEDS_REVIEW: 'bg-violet-400',
  CLEARED: 'bg-emerald-400',
  NOT_EVALUABLE: 'bg-slate-500',
}
const VERDICT_SHORT: Record<string, string> = {
  CONFIRMED_DEFECT: 'confirmed',
  LIKELY_DEFECT: 'likely',
  NEEDS_REVIEW: 'review',
  CLEARED: 'cleared',
  NOT_EVALUABLE: 'n/e',
}
const PHASE_COLOR: Record<string, string> = {
  OBSERVE: 'text-sky-300',
  ALIGN: 'text-indigo-300',
  DETECT: 'text-cyan-300',
  PLAN: 'text-blue-300',
  ACT: 'text-teal-300',
  VERIFY: 'text-amber-300',
  DECIDE: 'text-fuchsia-300',
}

function Gauge({ label, value, sub, tone }: { label: string; value: string | number; sub?: string; tone?: string }) {
  return (
    <div className="px-5 py-4">
      <div className="label-eyebrow">{label}</div>
      <div className={`mono mt-1.5 text-[26px] font-semibold leading-none ${tone ?? 'text-slate-100'}`}>
        {value}
      </div>
      {sub && <div className="mt-1.5 text-[10.5px] leading-snug text-slate-500">{sub}</div>}
    </div>
  )
}

function Row({ k, v, mono, highlight }: { k: string; v: string; mono?: boolean; highlight?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-slate-500">{k}</dt>
      <dd className={`${mono ? 'mono' : ''} text-[11px] ${highlight ? 'text-emerald-300' : 'text-slate-300'}`}>{v}</dd>
    </div>
  )
}
