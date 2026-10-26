import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { Scenario } from '../types'
import { Icon } from '../components/Icon'

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
    <div className="page-container">
      <div className="page-heading rise">
        <div><div className="label-eyebrow">01 / CONFIGURE INSPECTION</div>
        <h1>
          Give uncertainty a closer look.
        </h1>
        <p className="mt-1 max-w-2xl text-[13px] text-slate-400">
          Pick a seeded scenario, or upload your own reference/test pair. The agent never sees
          ground truth — it only gets the images, its OpenCV pipeline, and a tool budget.
        </p></div><span className="hidden rounded-lg border border-[#2b443f] bg-[#152622] p-3 text-emerald-200 md:block"><Icon name="scan" size={25}/></span>
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
                  aria-pressed={active}
                  onClick={() => { setSelected(s.id); setFiles({ reference: null, test: null, view2: null }) }}
                  className={`scenario-card ticked panel rise rise-${Math.min(idx + 1, 4)} overflow-hidden text-left ${
                    active ? 'ring-1 ring-cyan-400/60 glow-cyan' : ''
                  }`}
                >
                  <div className="relative h-36 overflow-hidden border-b border-[#1d2a3d] bg-[#0a0e13]">
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
                      <span className="mono rounded bg-black/70 px-1.5 py-0.5 text-[9px] text-slate-200 ring-1 ring-white/10">
                        {s.synthetic ? 'synthetic' : 'dataset image'}
                      </span>
                    </div>
                    {active && (
                      <span className="mono absolute right-3 top-2.5 rounded bg-cyan-400/20 px-1.5 py-0.5 text-[9px] text-cyan-200 ring-1 ring-cyan-400/50">
                        selected
                      </span>
                    )}
                  </div>
                  <div className="p-3.5">
                    <div className="flex items-start justify-between gap-3"><div className="text-[13.5px] font-medium text-slate-200">{s.title}</div><span className="mono text-[10px] text-slate-500">0{idx+1}</span></div>
                    <p className="mt-1 text-[11.5px] leading-relaxed text-slate-400">
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
            <div className="label-eyebrow">MISSION CONFIGURATION</div>
            <h2 className="mt-3 text-lg font-medium text-slate-100">{selected ? scenarios.find(s => s.id === selected)?.title : files.reference || files.test ? 'Custom board inspection' : 'Choose your evidence'}</h2>
            <p className="mt-2 text-[11px] leading-relaxed text-slate-400">{selected ? 'Synthetic demonstration. The agent receives images, not annotations or expected outcomes.' : 'Select a scenario, or supply a defect-free reference and a board to inspect.'}</p>
            <div className="hud-divider my-4"/>
            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-xs text-slate-400">tool-call budget</span>
              <span className="mono text-xl font-semibold text-cyan-300">{budget}</span>
            </div>
            <input
              type="range"
              aria-label="Tool-call budget"
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
              <div role="alert" className="mt-4 rounded-md border border-red-400/30 bg-red-400/10 p-2 text-xs text-red-300">
                {error}
              </div>
            )}

            <button
              disabled={!canStart || busy}
              onClick={start}
              className="primary-button mt-5 w-full"
            >
              {busy ? 'Starting inspection…' : 'Start inspection →'}
            </button>
            <p className="mt-3 text-center text-[10px] text-slate-400">No API key required · Local OpenCV processing</p>
          </div>
        </div>
      </div>
      {canStart && <div className="mobile-launchbar"><span className="text-xs text-slate-200">{selected ? scenarios.find(s => s.id === selected)?.title : 'Custom inspection'}<small className="mono mt-1 block text-[9px] text-slate-400">{budget} FOLLOW-UP CALLS MAX</small></span><button onClick={start} disabled={busy} className="primary-button">{busy ? 'Starting…' : 'Start inspection →'}</button></div>}
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
  const [error, setError] = useState<string | null>(null)
  const previewRef = useRef<HTMLImageElement>(null)
  useEffect(() => {
    if (!file) return
    const url = URL.createObjectURL(file)
    if (previewRef.current) previewRef.current.src = url
    return () => URL.revokeObjectURL(url)
  }, [file])
  const choose = (f: File | null) => {
    if (f && (!/\.(png|jpe?g|bmp|tiff?|webp)$/i.test(f.name) || f.size > 20 * 1024 * 1024)) {
      setError('Choose a PNG, JPG, BMP, TIFF or WebP image up to 20 MiB.'); return
    }
    setError(null); onFile(f)
  }
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Choose ${label}`}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inputRef.current?.click() } }}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setHover(true) }}
      onDragLeave={() => setHover(false)}
      onDrop={(e) => {
        e.preventDefault()
        setHover(false)
        const f = e.dataTransfer.files?.[0]
        if (f) choose(f)
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
          <img ref={previewRef} alt={`${label} preview`} className="mt-3 h-20 w-full rounded object-contain"/>
          <div className="mono mt-2 truncate text-[11px] text-emerald-300">{file.name}</div>
          <div className="mono text-[9px] text-slate-600">{(file.size / 1024).toFixed(0)} KB · click to replace</div>
        </>
      ) : (
        <>
          <div className="mt-2 text-[11.5px] text-slate-400">{hint}</div>
          <div className="mono mt-1 text-[9px] text-slate-400">drop image or click · max 20 MiB</div>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
        aria-label={label}
        className="hidden"
        onChange={(e) => { if (e.target.files?.[0]) choose(e.target.files[0]) }}
      />
      {error && <p role="alert" className="mt-2 text-[10px] text-red-200">{error}</p>}
    </div>
  )
}
