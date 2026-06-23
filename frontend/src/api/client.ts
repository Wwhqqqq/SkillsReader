const BASE = ''

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers as Record<string, string> },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json()
}

export function downloadSkillsExport(params: {
  format: 'csv' | 'xlsx'
  vendor?: string
  today_only?: boolean
  recent_only?: boolean
  last_official_scan?: boolean
}) {
  const q = new URLSearchParams()
  q.set('format', params.format)
  if (params.vendor) q.set('vendor', params.vendor)
  if (params.last_official_scan) q.set('last_official_scan', 'true')
  else if (params.recent_only) q.set('recent_only', 'true')
  else if (params.today_only) q.set('today_only', 'true')
  window.open(`/api/skills/export?${q.toString()}`, '_blank')
}

export function downloadSkillsBundle(params: {
  today_only?: boolean
  recent_only?: boolean
  scope?: 'domestic' | 'all'
}) {
  const q = new URLSearchParams()
  if (params.recent_only) q.set('recent_only', 'true')
  else if (params.today_only) q.set('today_only', 'true')
  if (params.scope) q.set('scope', params.scope)
  window.open(`/api/skills/export/bundle?${q.toString()}`, '_blank')
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  overview: () => request<any>('/api/stats/overview'),
  vendorStats: () => request<any>('/api/stats/vendors'),
  sources: () => request<any[]>('/api/sources'),
  updateSource: (id: string, body: object) =>
    request(`/api/sources/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  getGlobalScan: () => request<{ enabled: boolean }>('/api/sources/scan/global'),
  setGlobalScan: (enabled: boolean) =>
    request('/api/sources/scan/global', { method: 'PUT', body: JSON.stringify({ enabled }) }),
  skills: (params: Record<string, string | number | boolean> = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => q.set(k, String(v)))
    return request<any>(`/api/skills?${q}`)
  },
  digestPicks: (params: {
    date?: string
    top_n?: number
    vendors?: string[]
    regenerate?: boolean
  } = {}) => {
    const q = new URLSearchParams()
    if (params.date) q.set('digest_date', params.date)
    if (params.top_n) q.set('top_n', String(params.top_n))
    if (params.regenerate) q.set('regenerate', 'true')
    if (params.vendors?.length) q.set('vendors', params.vendors.join(','))
    return request<any>(`/api/digest/picks?${q.toString()}`)
  },
  digestPreview: (body: object) =>
    request<any>('/api/digest/preview', { method: 'POST', body: JSON.stringify(body) }),
  digestSchedule: () => request<any>('/api/digest/schedule'),
  setDigestSchedule: (body: object) =>
    request<any>('/api/digest/schedule', { method: 'PUT', body: JSON.stringify(body) }),
  digestConfig: () => request<any>('/api/digest/config'),
  triggerScan: (body: object = {}) =>
    request('/api/scan/trigger', { method: 'POST', body: JSON.stringify(body) }),
  officialScanStatus: () => request<any>('/api/scan/official/status'),
  officialScanPortals: () => request<any[]>('/api/scan/official/portals'),
  triggerOfficialScan: () =>
    request<any>('/api/scan/official', { method: 'POST' }),
  scanEvents: (limit = 100) => request<any[]>(`/api/scan/events?limit=${limit}`),
  pushPreview: (body: object) =>
    request<any>('/api/push/preview', { method: 'POST', body: JSON.stringify(body) }),
  pushTargets: () => request<any>('/api/push/targets'),
  pushSend: (body: object) =>
    request<any>('/api/push/send', { method: 'POST', body: JSON.stringify(body) }),
  pushHistory: () => request<any[]>('/api/push/history'),
  adapterProbe: (sourceId: string) =>
    request<any>('/api/debug/adapter-probe', {
      method: 'POST',
      body: JSON.stringify({ source_id: sourceId }),
    }),
  digestDiagnosis: () => request<any>('/api/debug/digest-diagnosis'),
  llmEnrich: (skillId: number) =>
    request<any>(`/api/debug/llm-enrich/${skillId}`, { method: 'POST' }),
}

export const testbenchApi = {
  init: () => request<any>('/api/testbench/init', { method: 'POST' }),
  reset: () => request<any>('/api/testbench/reset', { method: 'POST' }),
  platforms: () => request<any[]>('/api/testbench/platforms'),
  skills: () => request<any>('/api/testbench/skills'),
  createSkill: (body: object) =>
    request<any>('/api/testbench/skills', { method: 'POST', body: JSON.stringify(body) }),
  upsertSnapshots: (snapshot_date: string, items: object[]) =>
    request<any>('/api/testbench/snapshots', {
      method: 'PUT',
      body: JSON.stringify({ snapshot_date, items }),
    }),
  snapshotDates: () => request<string[]>('/api/testbench/snapshots/dates'),
  snapshots: (snapshot_date: string) =>
    request<any[]>(`/api/testbench/snapshots?snapshot_date=${snapshot_date}`),
  generateTimeline: (body: object) =>
    request<any>('/api/testbench/snapshots/timeline', { method: 'POST', body: JSON.stringify(body) }),
  simulate: (body: object) =>
    request<any>('/api/testbench/simulate', { method: 'POST', body: JSON.stringify(body) }),
}

export function wsScanEvents(onMessage: (data: any) => void): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/ws/scan-events`)
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data))
    } catch {
      /* ignore */
    }
  }
  return ws
}
