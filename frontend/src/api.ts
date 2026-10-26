import type { Inspection, InspectionEvent, Report, Scenario, Summary } from './types'

const BASE = ''

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body)
    } catch { /* keep statusText */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () =>
    req<{ status: string; opencv_version: string; version: string }>('/api/health'),
  systemInfo: () =>
    req<Record<string, unknown>>('/api/system/info'),
  scenarios: () => req<Scenario[]>('/api/demo/scenarios'),
  listInspections: () => req<Summary[]>('/api/inspections'),
  createFromScenario: (scenarioId: string, maxToolCalls: number) => {
    const fd = new FormData()
    fd.set('scenario_id', scenarioId)
    fd.set('max_tool_calls', String(maxToolCalls))
    return req<Summary>('/api/inspections', { method: 'POST', body: fd })
  },
  createFromUploads: (files: { reference: File; test: File; view2?: File | null }, maxToolCalls: number) => {
    const fd = new FormData()
    fd.set('reference', files.reference)
    fd.set('test', files.test)
    if (files.view2) fd.set('view2', files.view2)
    fd.set('max_tool_calls', String(maxToolCalls))
    return req<Summary>('/api/inspections', { method: 'POST', body: fd })
  },
  start: (id: string) => req<{ ok: boolean }>(`/api/inspections/${id}/start`, { method: 'POST' }),
  abort: (id: string) => req<{ ok: boolean }>(`/api/inspections/${id}/abort`, { method: 'POST' }),
  getInspection: (id: string) => req<Inspection>(`/api/inspections/${id}`),
  getReport: (id: string) => req<Report>(`/api/inspections/${id}/report`),
  getEvents: (id: string) => req<InspectionEvent[]>(`/api/inspections/${id}/events/all`).catch(() => []),
  addView: (id: string, file: File) => {
    const fd = new FormData()
    fd.set('view2', file)
    return req<{ ok: boolean }>(`/api/inspections/${id}/views`, { method: 'POST', body: fd })
  },
  rerun: (id: string) =>
    req<{ ok: boolean; inspection_id: string }>(`/api/inspections/${id}/rerun`, { method: 'POST' }),
  scenarioImage: (scenarioId: string, which: string = 'test') =>
    `/api/demo/scenarios/${scenarioId}/images/${which}`,
  submitReview: (id: string, regionId: string, decision: 'confirmed' | 'rejected', note: string) =>
    req<{ ok: boolean }>(`/api/inspections/${id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ region_id: regionId, decision, note }),
    }),
  imageUrl: (id: string, which: string) => `/api/inspections/${id}/images/${which}`,
  artifactUrl: (id: string, name: string) => `/api/inspections/${id}/artifacts/${name}`,
}

export function streamEvents(id: string, onEvent: (ev: InspectionEventT) => void, onDone: () => void): EventSource {
  const es = new EventSource(`${BASE}/api/inspections/${id}/events`)
  es.onmessage = (m) => {
    try {
      onEvent(JSON.parse(m.data))
    } catch { /* ignore malformed */ }
  }
  es.addEventListener('done', () => {
    onDone()
    es.close()
  })
  es.onerror = () => { /* EventSource reconnects; workspace recovers state and events by polling. */ }
  return es
}

type InspectionEventT = {
  seq: number
  ts: number
  phase: string
  type: string
  message: string
  evidence: Record<string, unknown>
  region_id: string | null
  artifacts: string[]
}
