import { useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { NewInspection } from './pages/NewInspection'
import { Workspace } from './pages/Workspace'
import { Icon } from './components/Icon'
import { api } from './api'

export default function App() {
  const [cv, setCv] = useState<string | null>(null)
  const [backendOk, setBackendOk] = useState<boolean | null>(null)
  const [clock, setClock] = useState('')
  const { pathname } = useLocation()
  const workspace = pathname.startsWith('/inspections/')
  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString('en-GB', { hour12: false }))
    tick(); const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [])
  useEffect(() => {
    let active = true
    const check = () => api.health().then(h => { if (active) { setCv(h.opencv_version); setBackendOk(true) } }).catch(() => { if (active) setBackendOk(false) })
    void check(); const t = setInterval(check, 15000)
    return () => { active = false; clearInterval(t) }
  }, [])
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <aside className="app-sidebar">
        <Link to="/" className="brand-lockup"><img src="/favicon.svg" alt=""/><span>CircuitSleuth<span className="brand-sub">VISION INTELLIGENCE</span></span></Link>
        <div className="sidebar-section">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <NavLink to="/" end className={({isActive}) => `side-link ${isActive ? 'active' : ''}`}><Icon name="grid"/><span>Overview</span><span className="nav-index">01</span></NavLink>
          <NavLink to="/new" className={({isActive}) => `side-link ${isActive ? 'active' : ''}`}><Icon name="scan"/><span>New inspection</span><span className="nav-index">02</span></NavLink>
          {workspace && <div className="side-link active"><Icon name="activity"/><span>Inspection workspace</span></div>}
        </nav>
        <div className="sidebar-note"><Icon name="layers" size={22}/><p>Observe.<br/>Investigate.<br/><span>Verify.</span></p><div>Active perception for<br/>printed circuit boards.</div></div>
        <div className="sidebar-bottom"><div className="flex items-center gap-2"><span className={`h-1.5 w-1.5 rounded-full ${backendOk ? 'bg-emerald-300' : 'bg-slate-500'}`}/><span>{backendOk ? 'INSPECTION ENGINE ONLINE' : backendOk === false ? 'ENGINE OFFLINE' : 'CONNECTING TO ENGINE'}</span></div><p>OpenCV 5 · MCP toolbelt</p><div className="mt-4 border-t border-white/8 pt-4">OPENCV AI COMPETITION <span className="text-slate-300">2026</span></div></div>
      </aside>
      <div className="app-content">
        <header className="app-topbar">
          <Link to="/" className="mobile-brand"><img src="/favicon.svg" alt="CircuitSleuth"/></Link>
          <div className="breadcrumb">Workspace <span>/</span> <strong>{workspace ? 'Inspection' : pathname === '/new' ? 'New inspection' : 'Overview'}</strong></div>
          <nav className="mobile-nav" aria-label="Mobile navigation"><Link to="/">Overview</Link><Link to="/new">New inspection</Link></nav>
          <div className="topbar-status"><span className="mono time-display">{clock} <span>LOCAL</span></span><span className={`engine-badge ${backendOk === false ? 'offline' : ''}`}><span className="status-light"/>{backendOk ? `OpenCV ${cv}` : backendOk === false ? 'Engine offline' : 'Connecting…'}</span><span className="operator-avatar" title="Local operator">CS</span></div>
        </header>
        <main id="main-content" className="main-content">
          <Routes><Route path="/" element={<Dashboard/>}/><Route path="/new" element={<NewInspection/>}/><Route path="/inspections/:id" element={<Workspace key={pathname}/>}/><Route path="*" element={<div className="page-container"><h1>Page not found</h1><Link className="primary-button mt-5" to="/">Back to overview</Link></div>}/></Routes>
        </main>
      </div>
    </div>
  )
}
