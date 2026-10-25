import { useState } from 'react'
import type { InspectionEvent } from '../types'
import { PhaseChip } from './ui'

const ICONS: Record<string, string> = {
  inspection_started: '◈',
  registration_completed: '⧉',
  registration_failed: '⊘',
  recovery_started: '↻',
  detection_completed: '◉',
  candidate_found: '▲',
  plan_selected: '➤',
  tool_executed: '⚙',
  additional_capture_required: '⚠',
  candidate_verified: '✓',
  human_review_requested: '☰',
  operator_review: '☰',
  inspection_completed: '■',
  inspection_aborted: '⊘',
  inspection_failed: '✗',
  report_generated: '▤',
  report_ready: '▤',
}

export function AgentFeed({ events, running, artifactUrl }: {
  events: InspectionEvent[]
  running: boolean
  artifactUrl: (name: string) => string
}) {
  const [expanded, setExpanded] = useState<number | null>(null)
  const ordered = [...events].reverse()
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-[#223047] px-3 py-2">
        <span className="text-xs font-semibold tracking-wide text-slate-300">Agent activity</span>
        {running && (
          <span className="flex items-center gap-1.5 text-[10px] text-cyan-300">
            <span className="pulse-dot inline-block h-1.5 w-1.5 rounded-full bg-cyan-400" /> live
          </span>
        )}
        <span className="ml-auto font-mono text-[10px] text-slate-500">{events.length} events</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {ordered.length === 0 && (
          <p className="px-2 py-6 text-center text-xs text-slate-500">Waiting for the agent…</p>
        )}
        <ol className="space-y-1">
          {ordered.map((ev) => {
            const isOpen = expanded === ev.seq
            return (
              <li key={ev.seq}>
                <button
                  onClick={() => setExpanded(isOpen ? null : ev.seq)}
                  className={`w-full rounded-md px-2 py-1.5 text-left transition-colors ${
                    isOpen ? 'bg-[#182334]' : 'hover:bg-[#141d2b]'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="w-4 text-center font-mono text-xs text-cyan-400">{ICONS[ev.type] ?? '·'}</span>
                    <PhaseChip phase={ev.phase} />
                    <span className="min-w-0 flex-1 truncate text-xs text-slate-300">{ev.message}</span>
                    <span className="shrink-0 font-mono text-[9px] text-slate-600">
                      {new Date(ev.ts * 1000).toLocaleTimeString()}
                    </span>
                  </div>
                  {ev.artifacts.length > 0 && (
                    <div className="mt-1 flex gap-1 pl-6">
                      {ev.artifacts.slice(0, 4).map((a) => (
                        <img
                          key={a}
                          src={artifactUrl(a)}
                          alt={a}
                          className="h-10 w-14 rounded border border-[#223047] object-cover"
                        />
                      ))}
                    </div>
                  )}
                  {isOpen && (
                    <pre className="mt-1.5 max-h-56 overflow-auto rounded bg-[#0a0e14] p-2 font-mono text-[10px] leading-relaxed text-slate-400">
{JSON.stringify(ev.evidence, null, 2)}
                    </pre>
                  )}
                </button>
              </li>
            )
          })}
        </ol>
      </div>
    </div>
  )
}
