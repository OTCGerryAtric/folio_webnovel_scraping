// One shared connection to the server's event stream, turned into a
// reactive store of jobs. EventSource reconnects by itself; on each
// (re)connect the store reseeds from /api/jobs so nothing is missed.

import { api } from './api'
import type { Job, JobEvent } from './types'

export interface LiveJob extends Job {
  log: string[]
  /** Units of progress per second, smoothed, for the ETA. */
  rate: number
  lastTick: number
  lastDone: number
}

const LOG_LINES = 200
type Listener = (job: LiveJob) => void

class JobsStore {
  jobs = $state<Record<string, LiveJob>>({})
  connected = $state(false)
  private finishers = new Set<Listener>()
  private source: EventSource | null = null

  connect() {
    if (this.source) return
    const source = new EventSource('/api/events')
    this.source = source
    source.onopen = () => {
      this.connected = true
      this.seed()
    }
    source.onerror = () => {
      this.connected = false
    }
    source.onmessage = message => this.handle(JSON.parse(message.data) as JobEvent)
  }

  private async seed() {
    try {
      for (const job of await api.jobs()) this.upsert(job, job.log ?? [])
    } catch {
      // the stream will retry
    }
  }

  private upsert(job: Job, log?: string[]) {
    const existing = this.jobs[job.id]
    const live: LiveJob = {
      ...job,
      log: log ?? existing?.log ?? [],
      rate: existing?.rate ?? 0,
      lastTick: existing?.lastTick ?? Date.now(),
      lastDone: existing?.lastDone ?? 0,
      progress: job.progress ?? existing?.progress ?? null,
    }
    const wasActive = existing && (existing.status === 'running' || existing.status === 'queued')
    this.jobs[job.id] = live
    const ended = job.status === 'done' || job.status === 'cancelled' || job.status === 'error'
    if (ended && wasActive) for (const fn of this.finishers) fn(live)
  }

  private handle(event: JobEvent) {
    if (event.type === 'job') {
      this.upsert(event.job)
      return
    }
    const job = this.jobs[event.job]
    if (!job) return
    if (event.type === 'log') {
      job.log = [...job.log.slice(-(LOG_LINES - 1)), event.line]
    } else {
      const now = Date.now()
      const p = event.progress
      if (p.done > job.lastDone && now > job.lastTick) {
        const instant = ((p.done - job.lastDone) * 1000) / (now - job.lastTick)
        job.rate = job.rate ? job.rate * 0.7 + instant * 0.3 : instant
      } else if (p.done < job.lastDone) {
        job.rate = 0 // a new phase, such as cleaning after downloading
      }
      job.lastDone = p.done
      job.lastTick = now
      job.progress = p
    }
  }

  get active(): LiveJob[] {
    return Object.values(this.jobs)
      .filter(j => j.status === 'running' || j.status === 'queued')
      .sort((a, b) => a.created - b.created)
  }

  byBook(name: string): LiveJob | undefined {
    return this.active.find(j => j.book === name)
  }

  /** Called with each job as it ends. Returns an unsubscribe function. */
  onFinish(fn: Listener): () => void {
    this.finishers.add(fn)
    return () => this.finishers.delete(fn)
  }

  /** Put a job just started into the store without waiting for its event. */
  track(job: Job) {
    if (!this.jobs[job.id]) this.upsert(job, job.log ?? [])
  }
}

export const jobsStore = new JobsStore()

export function percent(job: Job | undefined): number | null {
  const p = job?.progress
  if (!p || !p.total) return null
  return Math.min(100, Math.round((p.done / p.total) * 100))
}
