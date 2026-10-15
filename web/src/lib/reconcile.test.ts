import { expect, it } from 'vitest'
import { staleJobIds } from './reconcile'

it('finds jobs still shown as running that the server no longer knows - it was restarted', () => {
  const local = [
    { id: 'a', status: 'running' as const },
    { id: 'b', status: 'queued' as const },
    { id: 'c', status: 'done' as const },
    { id: 'd', status: 'running' as const },
  ]

  expect(staleJobIds(local, ['d'])).toEqual(['a', 'b'])
})
