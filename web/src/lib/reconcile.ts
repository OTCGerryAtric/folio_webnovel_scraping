import type { JobStatus } from './types'

/**
 * Jobs this page still shows as running that the server no longer lists.
 * The server keeps jobs in memory, so after a restart they are simply gone.
 */
export function staleJobIds(local: { id: string; status: JobStatus }[], serverIds: string[]): string[] {
  const known = new Set(serverIds)
  return local.filter(j => (j.status === 'running' || j.status === 'queued') && !known.has(j.id)).map(j => j.id)
}
