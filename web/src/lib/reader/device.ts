// Which device this browser is, for "your iPhone has moved on". Identifies,
// does not authenticate: access is the LAN key's job.

const KEY = 'folio-device'

export interface Device {
  id: string
  name: string
}

export function deviceName(ua: string): string {
  const os = /iPhone/.test(ua) ? 'iPhone'
    : /iPad/.test(ua) ? 'iPad'
    : /Android/.test(ua) ? 'Android'
    : /Windows/.test(ua) ? 'Windows'
    : /Mac OS X|Macintosh/.test(ua) ? 'Mac'
    : /Linux/.test(ua) ? 'Linux'
    : ''
  const browser = /Edg\//.test(ua) ? 'Edge'
    : /Firefox\//.test(ua) ? 'Firefox'
    : /Chrome\//.test(ua) ? 'Chrome'
    : /Safari\//.test(ua) ? 'Safari'
    : ''
  return [os, browser].filter(Boolean).join(' · ') || 'Browser'
}

function newId(): string {
  const random = globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)
  return `d-${random.replace(/-/g, '').slice(0, 10)}`
}

let memory: Device | null = null

export function getDevice(): Device {
  if (memory) return memory
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? 'null')
    if (saved && typeof saved.id === 'string' && typeof saved.name === 'string') return (memory = saved)
  } catch {
    // unreadable or unavailable: a fresh identity for this visit
  }
  memory = { id: newId(), name: deviceName(navigator.userAgent) }
  store(memory)
  return memory
}

export function renameDevice(name: string): Device {
  const device = { ...getDevice(), name: name.trim().slice(0, 80) || deviceName(navigator.userAgent) }
  memory = device
  store(device)
  return device
}

function store(device: Device) {
  try {
    localStorage.setItem(KEY, JSON.stringify(device))
  } catch {
    // private mode: it lasts this visit
  }
}
