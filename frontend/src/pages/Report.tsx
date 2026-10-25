import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Inspection, Report } from '../types'
import { VerdictChip } from '../components/ui'
import type { Verdict } from '../types'

export function ReportView({ inspectionId, ins }: { inspectionId: string; ins: Inspection }) {
  const [report, setReport] = useState<Report | null>(ins.report)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    if (ins.report) { setReport(ins.report); return }
    api.getReport(inspectionId).then(setReport).catch(() => setMissing(true))
  }, [inspectionId, ins.report])

  if (missing || !report) {
    return (
      <p className="p-6 text-center text-xs text-slate-500">
        The report is generated when the inspection completes.
      </p>
    )
  }

  const download = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `circuitsleuth-report-${report.inspection_id}.json`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const reg = report.registration
  return (
    <div className="h-full overflow-y-auto p-3 text-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold tracking-wide text-slate-300">
          Inspection report · {new Date(report.generated_at).toLocaleString()}
        </h3>
        <button
          onClick={download}
          className="rounded-md bg-cyan-400/10 px-2.5 py-1 text-[11px] text-cyan-300 ring-1 ring-cyan-400/30 hover:bg-cyan-400/20"
        >
          Download JSON
        </button>
      </div>

      <div className="mt-2 grid grid-cols-3 gap-2 text-[11px]">
        <Info k="Stop reason" v={report.stop_reason} />
        <Info k="Tool calls" v={String(report.tool_calls_used)} />
        <Info k="Iterations" v={String(report.iterations)} />
      </div>

      {reg && (
        <div className="panel mt-3 p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">Registration</div>
          <div className="mt-1.5 grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[11px] text-slate-300">
            <span>detector: {reg.detector}</span>
            <span>quality: <span className="text-cyan-300">{reg.quality}</span></span>
            <span>inliers: {reg.inliers ?? '—'}</span>
            <span>residual: {reg.mean_residual_px != null ? `${reg.mean_residual_px}px` : '—'}</span>
            <span>coverage: {reg.coverage_score ?? '—'}</span>
            {reg.photometric_score != null && <span>photometric: {reg.photometric_score}</span>}
          </div>
          {reg.attempts && (
            <div className="mt-1 text-[10px] text-slate-500">strategies: {reg.attempts.join(' → ')}</div>
          )}
        </div>
      )}

      <h4 className="mt-4 text-xs font-semibold tracking-wide text-slate-300">Verdicts</h4>
      <div className="mt-1.5 space-y-1.5">
        {report.verdicts.length === 0 && (
          <p className="text-xs text-slate-500">No candidate regions were detected.</p>
        )}
        {report.verdicts.map((v) => (
          <div key={v.region_id} className="rounded-lg ring-1 ring-[#223047] p-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-cyan-300">{v.region_id}</span>
              <VerdictChip status={v.status as Verdict} small />
              {v.label && (
                <span className="rounded bg-slate-400/10 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
                  {v.label}
                </span>
              )}
              <span className="ml-auto font-mono text-[10px] text-slate-500">
                bbox [{v.bbox.x},{v.bbox.y},{v.bbox.w},{v.bbox.h}]
              </span>
            </div>
            {v.label_basis && <p className="mt-1 text-[11px] text-slate-400">{v.label_basis}</p>}
            <div className="mt-1 flex flex-wrap gap-1">
              {v.tools_used.map((t) => (
                <span key={t} className="rounded bg-black/30 px-1 py-0.5 font-mono text-[9px] text-slate-400">{t}</span>
              ))}
              <span className="ml-auto font-mono text-[9px] text-slate-500">
                diff {v.difference_score.toFixed(2)} · mismatch {v.structural_mismatch_score.toFixed(2)} · {v.evidence.length} evidence
              </span>
            </div>
          </div>
        ))}
      </div>

      {report.review_requests.length > 0 && (
        <>
          <h4 className="mt-4 text-xs font-semibold tracking-wide text-slate-300">Human review requests</h4>
          <ul className="mt-1.5 space-y-1">
            {report.review_requests.map((r, i) => (
              <li key={i} className="rounded-lg bg-violet-400/5 p-2 text-[11px] text-slate-300 ring-1 ring-violet-400/20">
                <span className="font-mono text-violet-300">{r.region_id}</span> — {r.reason}
                {r.resolved && <span className="ml-2 text-emerald-300">(operator: {r.resolved})</span>}
              </li>
            ))}
          </ul>
        </>
      )}

      <h4 className="mt-4 text-xs font-semibold tracking-wide text-slate-300">Limitations</h4>
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[11px] text-slate-500">
        {report.limitations.map((l, i) => <li key={i}>{l}</li>)}
      </ul>
    </div>
  )
}

function Info({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded-md bg-black/20 px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-wider text-slate-500">{k}</div>
      <div className="font-mono text-slate-300">{v}</div>
    </div>
  )
}
