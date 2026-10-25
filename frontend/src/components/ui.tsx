import type { Verdict } from '../types'

export const VERDICT_STYLE: Record<Verdict, { label: string; color: string; bg: string; ring: string }> = {
  SUSPECTED: { label: 'Suspected', color: 'text-cyan-300', bg: 'bg-cyan-400/10', ring: 'ring-cyan-400/40' },
  CONFIRMED_DEFECT: { label: 'Confirmed defect', color: 'text-red-300', bg: 'bg-red-400/10', ring: 'ring-red-400/40' },
  LIKELY_DEFECT: { label: 'Likely defect', color: 'text-amber-300', bg: 'bg-amber-400/10', ring: 'ring-amber-400/40' },
  CLEARED: { label: 'Cleared', color: 'text-emerald-300', bg: 'bg-emerald-400/10', ring: 'ring-emerald-400/40' },
  NEEDS_REVIEW: { label: 'Needs review', color: 'text-violet-300', bg: 'bg-violet-400/10', ring: 'ring-violet-400/40' },
  NOT_EVALUABLE: { label: 'Not evaluable', color: 'text-slate-400', bg: 'bg-slate-400/10', ring: 'ring-slate-400/40' },
}

export function VerdictChip({ status, small }: { status: Verdict; small?: boolean }) {
  const s = VERDICT_STYLE[status] ?? VERDICT_STYLE.SUSPECTED
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md ring-1 ${s.bg} ${s.ring} ${s.color} ${
        small ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs'
      } font-medium whitespace-nowrap`}
    >
      {s.label}
    </span>
  )
}

export function StatusDot({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: 'bg-emerald-400',
    running: 'bg-cyan-400 pulse-dot',
    created: 'bg-slate-500',
    failed: 'bg-red-400',
  }
  return <span className={`inline-block h-2 w-2 rounded-full ${map[status] ?? 'bg-slate-500'}`} />
}

export function ScoreBar({ label, value, max = 1, tone }: { label: string; value: number; max?: number; tone: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-36 shrink-0 text-slate-400">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded bg-slate-700/50">
        <div className={`h-full rounded ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-12 text-right font-mono text-slate-300">{value.toFixed(2)}</span>
    </div>
  )
}

export function PhaseChip({ phase }: { phase: string }) {
  const map: Record<string, string> = {
    OBSERVE: 'bg-sky-400/10 text-sky-300 ring-sky-400/40',
    ALIGN: 'bg-indigo-400/10 text-indigo-300 ring-indigo-400/40',
    DETECT: 'bg-cyan-400/10 text-cyan-300 ring-cyan-400/40',
    PLAN: 'bg-blue-400/10 text-blue-300 ring-blue-400/40',
    ACT: 'bg-teal-400/10 text-teal-300 ring-teal-400/40',
    VERIFY: 'bg-amber-400/10 text-amber-300 ring-amber-400/40',
    DECIDE: 'bg-fuchsia-400/10 text-fuchsia-300 ring-fuchsia-400/40',
  }
  return (
    <span className={`rounded px-1.5 py-0.5 font-mono text-[10px] ring-1 ${map[phase] ?? 'bg-slate-400/10 text-slate-300 ring-slate-400/40'}`}>
      {phase}
    </span>
  )
}
