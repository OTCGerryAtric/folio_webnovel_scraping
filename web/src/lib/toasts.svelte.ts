// Short-lived messages in the corner, optionally with one action.

export type Tone = 'ok' | 'bad' | 'neutral'

export interface Toast {
  id: number
  tone: Tone
  title: string
  body?: string
  action?: { label: string; href?: string; download?: boolean; run?: () => void }
}

const LIFETIME = 6000

class Toasts {
  items = $state<Toast[]>([])
  private next = 1
  private timers = new Map<number, ReturnType<typeof setTimeout>>()

  show(toast: Omit<Toast, 'id'>, lifetime = LIFETIME): number {
    const id = this.next++
    this.items = [...this.items.slice(-3), { ...toast, id }]
    this.schedule(id, lifetime)
    return id
  }

  schedule(id: number, lifetime = LIFETIME) {
    clearTimeout(this.timers.get(id))
    this.timers.set(id, setTimeout(() => this.dismiss(id), lifetime))
  }

  hold(id: number) {
    clearTimeout(this.timers.get(id))
  }

  dismiss(id: number) {
    clearTimeout(this.timers.get(id))
    this.timers.delete(id)
    this.items = this.items.filter(t => t.id !== id)
  }
}

export const toasts = new Toasts()
