import { useState } from 'react'
import type { Candidate, Evidence } from '../types'
import { ScoreBar, VerdictChip } from './ui'

const KIND_LABEL: Record<string, string> = {
  difference_severity: 'Difference severity',
  structural_mismatch: 'Structural mismatch',
  edge_topology: 'Edge topology',
  independent_view: 'Independent view',
  local_realignment: 'Local realignment',
  illumination_confound: 'Illumination confound',
}

export function RegionDetail({ candidate, onSubmitReview, artifactUrl }: {
  candidate: Candidate
  onSubmitReview: (regionId: string, decision: 'confirmed' | 'rejected', note: string) => Promise<void>
  artifactUrl: (name: string) => string
}) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [openEvidence, setOpenEvidence] = useState<string | null>(candidate.evidence[0]?.source_tool ?? null)

  const review = async (decision: 'confirmed' | 'rejected') => {
    setBusy(true)
    try {
      await onSubmitReview(candidate.region_id, decision, note)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto p-3 text-sm">
      <div className="flex items-center gap-2">
        <span className="font-mono text-lg font-semibold text-cyan-300">{candidate.region_id}</span>
        <VerdictChip status={candidate.status} />
        {candidate.label && (
          <span className="rounded bg-slate-400/10 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
            {candidate.label}
          </span>
        )}
      </div>
      {candidate.label_basis && (
        <p className="mt-1 text-xs text-slate-400">Basis: {candidate.label_basis}</p>
      )}

      <div className="mt-3 space-y-1.5">
        <ScoreBar label="Difference score" value={candidate.difference_score} tone="bg-cyan-400" />
        <ScoreBar label="Structural mismatch" value={candidate.structural_mismatch_score} tone="bg-indigo-400" />
        <ScoreBar label="Evidence quality" value={candidate.evidence_quality_score} tone="bg-teal-400" />
        <div className="flex gap-3 pl-[9.5rem] text-[10px] text-slate-500">
          <span>area {candidate.area_px}px²</span>
          <span>bbox [{candidate.bbox.join(', ')}]</span>
        </div>
        {(candidate.illumination_suspect || candidate.touches_invalid_warp_region) && (
          <div className="flex gap-2 pt-1">
            {candidate.illumination_suspect && (
              <span className="rounded bg-amber-400/10 px-1.5 py-0.5 text-[10px] text-amber-300 ring-1 ring-amber-400/40">
                illumination suspect
              </span>
            )}
            {candidate.touches_invalid_warp_region && (
              <span className="rounded bg-slate-400/10 px-1.5 py-0.5 text-[10px] text-slate-300 ring-1 ring-slate-400/40">
                at warp border
              </span>
            )}
          </div>
        )}
      </div>

      <h4 className="mt-4 text-xs font-semibold tracking-wide text-slate-300">Evidence trail</h4>
      <div className="mt-1.5 space-y-1.5">
        {candidate.evidence.length === 0 && (
          <p className="text-xs text-slate-500">No secondary analysis yet.</p>
        )}
        {candidate.evidence.map((e, i) => (
          <EvidenceCard
            key={i}
            ev={e}
            open={openEvidence === e.source_tool + i}
            onToggle={() => setOpenEvidence(openEvidence === e.source_tool + i ? null : e.source_tool + i)}
            artifactUrl={artifactUrl}
          />
        ))}
      </div>

      {candidate.notes.length > 0 && (
        <>
          <h4 className="mt-4 text-xs font-semibold tracking-wide text-slate-300">Notes</h4>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-slate-400">
            {candidate.notes.map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </>
      )}

      {(candidate.status === 'NEEDS_REVIEW' || candidate.status === 'LIKELY_DEFECT') && (
        <div className="mt-4 rounded-lg border border-violet-400/30 bg-violet-400/5 p-3">
          <h4 className="text-xs font-semibold text-violet-300">Operator decision</h4>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="optional note…"
            className="mt-2 w-full rounded-md border border-[#223047] bg-[#0a0e14] px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-cyan-400/50"
          />
          <div className="mt-2 flex gap-2">
            <button
              disabled={busy}
              onClick={() => review('confirmed')}
              className="rounded-md bg-red-400/15 px-3 py-1.5 text-xs font-medium text-red-300 ring-1 ring-red-400/40 hover:bg-red-400/25 disabled:opacity-50"
            >
              Confirm defect
            </button>
            <button
              disabled={busy}
              onClick={() => review('rejected')}
              className="rounded-md bg-emerald-400/10 px-3 py-1.5 text-xs font-medium text-emerald-300 ring-1 ring-emerald-400/40 hover:bg-emerald-400/20 disabled:opacity-50"
            >
              Clear region
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function EvidenceCard({ ev, open, onToggle, artifactUrl }: {
  ev: Evidence
  open: boolean
  onToggle: () => void
  artifactUrl: (name: string) => string
}) {
  const tone = ev.supports_defect === true
    ? 'text-red-300 ring-red-400/30'
    : ev.supports_defect === false
      ? 'text-emerald-300 ring-emerald-400/30'
      : 'text-slate-300 ring-slate-400/30'
  const verdictWord = ev.supports_defect === true
    ? 'supports defect'
    : ev.supports_defect === false
      ? 'refutes defect'
      : 'inconclusive'
  return (
    <div className={`rounded-lg ring-1 ${tone}`}>
      <button onClick={onToggle} className="w-full px-2.5 py-2 text-left">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium">{KIND_LABEL[ev.evidence_kind] ?? ev.evidence_kind}</span>
          <span className="rounded bg-black/30 px-1 py-0.5 font-mono text-[9px] text-slate-400">{ev.source_tool}</span>
          {ev.honesty && ev.honesty !== 'reprocess' && (
            <span className="rounded bg-sky-400/10 px-1 py-0.5 font-mono text-[9px] text-sky-300">{ev.honesty}</span>
          )}
          <span className="ml-auto text-[10px] opacity-80">{verdictWord}</span>
        </div>
        <p className="mt-0.5 text-[11px] leading-snug opacity-90">{ev.summary}</p>
      </button>
      {open && (
        <div className="border-t border-white/5 px-2.5 py-2">
          {ev.artifact && (
            <img src={artifactUrl(ev.artifact)} alt={ev.artifact} className="mb-2 max-h-40 w-full rounded object-contain" />
          )}
          <pre className="max-h-44 overflow-auto rounded bg-black/40 p-2 font-mono text-[10px] leading-relaxed text-slate-400">
{JSON.stringify(ev.metrics, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
