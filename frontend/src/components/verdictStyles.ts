import type { Verdict } from '../types'

export const VERDICT_STYLE: Record<Verdict, { label: string; color: string; bg: string; ring: string }> = {
  SUSPECTED: { label: 'Suspected', color: 'text-cyan-300', bg: 'bg-cyan-400/10', ring: 'ring-cyan-400/40' },
  CONFIRMED_DEFECT: { label: 'Confirmed defect', color: 'text-red-300', bg: 'bg-red-400/10', ring: 'ring-red-400/40' },
  LIKELY_DEFECT: { label: 'Likely defect', color: 'text-amber-300', bg: 'bg-amber-400/10', ring: 'ring-amber-400/40' },
  CLEARED: { label: 'Cleared', color: 'text-emerald-300', bg: 'bg-emerald-400/10', ring: 'ring-emerald-400/40' },
  NEEDS_REVIEW: { label: 'Needs review', color: 'text-violet-300', bg: 'bg-violet-400/10', ring: 'ring-violet-400/40' },
  NOT_EVALUABLE: { label: 'Not evaluable', color: 'text-slate-400', bg: 'bg-slate-400/10', ring: 'ring-slate-400/40' },
}

