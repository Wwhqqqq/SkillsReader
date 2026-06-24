/** 后端时间多为 UTC naive ISO 字符串，统一转为北京时间展示。 */

function parseBackendTime(iso: string): Date | null {
  const trimmed = iso.trim()
  if (!trimmed) return null
  const hasTz = /[Zz]|[+-]\d{2}:\d{2}$/.test(trimmed)
  const normalized = hasTz ? trimmed : `${trimmed}Z`
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

/** YYYY-MM-DD HH:mm:ss（北京时间） */
export function formatBeijingTime(iso: string | null | undefined): string {
  if (!iso) return '--'
  const date = parseBackendTime(iso)
  if (!date) return iso.slice(0, 19).replace('T', ' ')
  return date.toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai' }).replace('T', ' ')
}

/** HH:mm:ss（北京时间，用于日志行） */
export function formatBeijingTimeOnly(iso: string | null | undefined): string {
  const full = formatBeijingTime(iso)
  return full === '--' ? '--' : full.slice(11)
}
