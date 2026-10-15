// Plain-English one-liners for jobs, shared by the activity list and toasts.

import type { ActivityRecord, JobKind } from './types'

export const KIND_LABEL: Record<JobKind, string> = {
  download: 'Download',
  clean: 'Clean',
  build: 'Build',
  update: 'Update',
}

export const KIND_ACTIVE: Record<JobKind, string> = {
  download: 'Downloading',
  clean: 'Cleaning',
  build: 'Building',
  update: 'Updating',
}

export function describeJob(job: Pick<ActivityRecord, 'kind' | 'status' | 'summary' | 'error'>): string {
  if (job.status === 'error') return job.error ?? 'Failed'
  const s = job.summary ?? {}
  const parts: string[] = []
  if (s.fetched !== undefined) parts.push(s.fetched ? `Downloaded ${s.fetched.toLocaleString('en-GB')}` : 'Nothing new')
  if (s.cleaned !== undefined) parts.push(`Cleaned ${s.cleaned.toLocaleString('en-GB')}`)
  if (s.files?.length) parts.push(s.files.length === 1 ? `Built ${s.files[0]}` : `Built ${s.files.length} files`)
  const text = parts.join(' · ') || 'Done'
  return job.status === 'cancelled' ? `Stopped · ${text}` : text
}
