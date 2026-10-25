import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { Scenario } from '../types'

export function NewInspection() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [budget, setBudget] = useState(12)
  const [files, setFiles] = useState<{ reference: File | null; test: File | null; view2: File | null }>({
    reference: null, test: null, view2: null,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const nav = useNavigate()

  useEffect(() => { api.scenarios().then(setScenarios).catch((e) => setError(e.message)) }, [])

  const start = async () => {
    setBusy(true)
    setError(null)
    try {
      const summary = selected
        ? await api.createFromScenario(selected, budget)
        : await api.createFromUploads(
            { reference: files.reference!, test: files.test!, view2: files.view2 },
            budget,
          )
      await api.start(summary.id)
      nav(`/inspections/${summary.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  const canStart = selected || (files.reference && files.test)

  return (
    <div className="mx-auto max-w-7xl px-6 py-7">
      <div className="rise">
        <div className="label-eyebrow">new run</div>
        <h1 className="mt-1 text-[26px] font-semibold tracking-tight text-slate-100">
          What should the agent look at?
        </h1>
        <p className="mt-1 max-w-2xl text-[13px] text-slate-400">
          Pick a seeded scenario, or upload your own reference/test pair. The agent never sees
          ground truth — it only gets the images, its OpenCV pipeline, and a tool budget.
        </p>
      </div>

      <div className="mt-7 grid gap-6 lg:grid-cols-[1fr_320px]">
        <div>
          <div className="label-eyebrow rise rise-1">scenario library · synthetic, reproducible</div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {scenarios.map((s, idx) => {
              const active = selected === s.id
              return (
                <button
                  key={s.id}
                  onClick={() => { setSelected(s.id); setFiles({ reference: null, test: null, view2: null }) }}
                  className={`scenario-card ticked panel rise rise-${Math.min(idx + 1, 4)} overflow-hidden text-left ${
                    active ? 'ring-1 ring-cyan-400/60 glow-cyan' : ''
                  }`}
                >
                  <div className="relative h-28 overflow-hidden border-b border-[#1d2a3d] bg-[#0a0e13]">
                    <img
                      src={api.scenarioImage(s.id, 'test')}
                      alt={s.title}
                      loading="lazy"
                      className="h-full w-full object-cover opacity-80"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0d131c] via-transparent to-transparent" />
                    <div className="absolute left-3 top-2.5 flex gap-1.5">
                      <span className={`mono rounded px-1.5 py-0.5 text-[9px] ring-1 ${
                        s.has_secondary_view
                          ? 'bg-sky-400/15 text-sky-300 ring-sky-400/40'
                          : 'bg-slate-500/15 text-slate-400 ring-slate-400/40'
                      }`}>
                        {s.has_secondary_view ? '2 captures' : '1 capture'}
                      </span>
                      <span className="mono rounded bg-black/50 px-1.5 py-0.5 text-[9px] text-slate-400 ring-1 ring-white/10">
                        synthetic
                      </span>
                    </div>
                    {active && (
                      <span className="mono absolute right-3 top-2.5 rounded bg-cyan-400/20 px-1.5 py-0.5 text-[9px] text-cyan-200 ring-1 ring-cyan-400/50">
                        selected
                      </span>
                    )}
                  </div>
                  <div className="p-3.5">
                    <div className="text-[13.5px] font-medium text-slate-200">{s.title}</div>
                    <p className="mt-1 line-clamp-2 text-[11.5px] leading-relaxed text-slate-500">
                      {s.description}
                    </p>
                    <div className="mono mt-2.5 flex flex-wrap gap-x-3 gap-y-1 text-[9.5px] text-slate-500">
                      {s.expected.slice(0, 2).map((e, i) => (
                        <span key={i} className="flex items-center gap-1">
                          <span className="text-cyan-500/80">▸</span> {e}
                        </span>
                      ))}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>

          <div className="label-eyebrow rise rise-2 mt-7">or bring your own board</div>
          <div className="ticked panel rise rise-2 mt-3 grid gap-4 p-4 md:grid-cols-3">
            <DropSlot
              label="reference image"
              hint="defect-free board"
              required
              file={files.reference}
              onFile={(f) => { setFiles((p) => ({ ...p, reference: f })); setSelected(null) }}
            />
            <DropSlot
              label="test image"
              hint="board under inspection"
              required
              file={files.test}
              onFile={(f) => { setFiles((p) => ({ ...p, test: f })); setSelected(null) }}
            />
            <DropSlot
              label="secondary view"
              hint="optional — new optical evidence"
              file={files.view2}
              onFile={(f) => { setFiles((p) => ({ ...p, view2: f })); setSelected(null) }}
            />
          </div>
        </div>

        {/* config rail */}
        <div className="lg:sticky lg:top-6 lg:h-fit">
          <div className="ticked panel rise rise-2 p-4">
            <div className="label-eyebrow">inspection limits</div>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-xs text-slate-400">tool-call budget</span>
              <span className="mono text-xl font-semibold text-cyan-300">{budget}</span>
            </div>
            <input
              type="range"
              min={3}
              max={30}
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              className="mt-2 w-full accent-cyan-400"
            />
            <p className="mt-2.5 text-[11px] leading-relaxed text-slate-500">
              Each call is one agent decision: a confound test, an independent-view comparison, an
              edge analysis… When the budget runs dry, unfinished regions go to human review — the
              agent does not guess.
            </p>

            <div className="hud-divider my-4" />

            <ol className="space-y-2 text-[11px] text-slate-400">
              {[
                ['align', 'SIFT + RANSAC + ECC, verified photometrically'],
                ['detect', 'diff ⊗ structural mismatch, confound-aware'],
                ['plan · act · verify', 'evidence-driven tool selection'],
                ['decide', 'verdicts with recorded basis, or escalation'],
              ].map(([k, v], i) => (
                <li key={i} className="flex gap-2.5">
                  <span className="mono mt-0.5 w-4 text-right text-[9px] text-cyan-500/70">{i + 1}</span>
                  <span>
                    <span className="mono text-[10px] uppercase tracking-wider text-slate-300">{k}</span>
                    <br />
                    <span className="text-slate-500">{v}</span>
                  </span>
                </li>
              ))}
            </ol>

            {error && (
              <div className="mt-4 rounded-md border border-red-400/30 bg-red-400/10 p-2 text-xs text-red-300">
                {error}
              </div>
            )}

            <button
              disabled={!canStart || busy}
              onClick={start}
              className="glow-cyan mt-5 w-full rounded-lg bg-cyan-400/15 py-2.5 text-sm font-medium text-cyan-100 ring-1 ring-cyan-400/40 transition hover:bg-cyan-400/25 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy ? 'starting…' : 'Start inspection →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function DropSlot({ label, hint, required, file, onFile }: {
  label: string
  hint: string
  required?: boolean
  file: File | null
  onFile: (f: File | null) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [hover, setHover] = useState(false)
  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setHover(true) }}
      onDragLeave={() => setHover(false)}
      onDrop={(e) => {
        e.preventDefault()
        setHover(false)
        const f = e.dataTransfer.files?.[0]
        if (f) onFile(f)
      }}
      className={`flex cursor-pointer flex-col rounded-lg border border-dashed px-3.5 py-4 transition ${
        hover
          ? 'border-cyan-400/60 bg-cyan-400/5'
          : file
            ? 'border-emerald-400/40 bg-emerald-400/5'
            : 'border-[#2b3d58] bg-[#0a0e14] hover:border-cyan-400/30'
      }`}
    >
      <div className="label-eyebrow">
        {label} {required && <span className="text-cyan-400">*</span>}
      </div>
      {file ? (
        <>
          <div className="mono mt-2 truncate text-[11px] text-emerald-300">{file.name}</div>
          <div className="mono text-[9px] text-slate-600">{(file.size / 1024).toFixed(0)} KB · click to replace</div>
        </>
      ) : (
        <>
          <div className="mt-2 text-[11.5px] text-slate-400">{hint}</div>
          <div className="mono text-[9px] text-slate-600">drop PNG/JPG or click · max 20 MB</div>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
    </div>
  )
}
