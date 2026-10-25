import { useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { NewInspection } from './pages/NewInspection'
import { Workspace } from './pages/Workspace'
import { api } from './api'

export default function App() {
  const [cv, setCv] = useState<string | null>(null)
  const [backendOk, setBackendOk] = useState<boolean | null>(null)
  const [clock, setClock] = useState('')
  const { pathname } = useLocation()

  useEffect(() => {
    const tick = () =>
      setClock(new Date().toLocaleTimeString('en-GB', { hour12: false }))
    tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    api.health()
      .then((h) => { setCv(h.opencv_version); setBackendOk(true) })
      .catch(() => setBackendOk(false))
  }, [])

  const onWorkspace = pathname.startsWith('/inspections/')

  return (
    <div className="flex h-full flex-col">
      <header className="relative z-10 flex h-14 shrink-0 items-center gap-5 border-b border-[#1d2a3d] bg-[#0a1018]/85 px-5 backdrop-blur">
        <Link to="/" className="group flex items-center gap-2.5">
          <span className="relative flex h-8 w-8 items-center justify-center">
            <img src="/favicon.svg" alt="" className="h-8 w-8" />
            <span className="absolute inset-0 rounded-lg opacity-0 transition group-hover:opacity-100 group-hover:glow-cyan" />
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-slate-100">
            CircuitSleuth
          </span>
          <span className="mono hidden border-l border-[#1d2a3d] pl-3 text-[9px] uppercase tracking-[0.2em] text-slate-500 lg:inline">
            active-perception pcb inspection
          </span>
        </Link>

        {!onWorkspace && (
          <nav className="ml-2 flex items-center gap-1">
            <TabLink to="/" label="Overview" end />
            <TabLink to="/new" label="New inspection" />
          </nav>
        )}

        <div className="mono ml-auto flex items-center gap-4 text-[10px]">
          <span className="hidden text-slate-600 md:inline" suppressHydrationWarning>{clock}</span>
          {backendOk === false && (
            <span className="flex items-center gap-1.5 rounded bg-red-400/10 px-2 py-1 text-red-300 ring-1 ring-red-400/40">
              <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
              backend offline — run scripts\run_dev.bat
            </span>
          )}
          {backendOk === true && (
            <span className="flex items-center gap-1.5 rounded bg-emerald-400/8 px-2 py-1 text-emerald-300/90 ring-1 ring-emerald-400/25">
              <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-emerald-400" />
              opencv {cv}
            </span>
          )}
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<NewInspection />} />
          <Route path="/inspections/:id" element={<Workspace />} />
        </Routes>
      </main>
    </div>
  )
}

function TabLink({ to, label, end }: { to: string; label: string; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
          isActive
            ? 'bg-cyan-400/10 text-cyan-200 ring-1 ring-cyan-400/30'
            : 'text-slate-400 hover:text-slate-100'
        }`
      }
    >
      {label}
    </NavLink>
  )
}
