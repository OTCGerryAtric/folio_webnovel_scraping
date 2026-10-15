<script lang="ts">
  // The reader plus keeping its place: resume on opening, save as you read,
  // and ask - never jump silently - when another device has moved on.
  import { onMount, untrack } from 'svelte'
  import { PositionSync, type OwnPlace } from '../lib/reader/positionSync.svelte'
  import type { Place, Theirs } from '../lib/reader/sync'
  import ConflictBanner from '../components/reader/ConflictBanner.svelte'
  import ContinuePrompt from '../components/reader/ContinuePrompt.svelte'
  import Reader from './Reader.svelte'

  let { name, chapter }: { name: string; chapter: number | null } = $props()

  // Rebuilt for each book and chapter link (keyed in App).
  const sync = new PositionSync(untrack(() => name))
  let reader = $state<ReturnType<typeof Reader>>()
  let asking = $state<{ theirs: Theirs; ours: OwnPlace; answer: (p: Place) => void } | null>(null)

  async function start(_list: unknown, explicit: boolean) {
    let decision
    try {
      decision = await sync.open() // also catches up on the latest revision
    } catch {
      return null // the PC did not answer: start at the beginning; saving will retry
    }
    if (explicit) return null // a chapter was chosen: open it; the next save moves the place there
    if (decision.kind === 'go') return { ...decision.place, note: decision.note }
    if (decision.kind === 'ask') {
      const ask = decision
      return new Promise<Place>(answer => (asking = { theirs: ask.theirs, ours: ask.ours as OwnPlace, answer }))
    }
    return null
  }

  function choose(which: 'theirs' | 'ours') {
    if (!asking) return
    const { theirs, ours, answer } = asking
    asking = null
    answer(
      which === 'theirs'
        ? { chapter: theirs.resolvedChapter, paragraph: theirs.resolvedParagraph, offset: theirs.resolvedOffset }
        : { chapter: ours.chapter, paragraph: ours.paragraph, offset: ours.offset },
    )
  }

  async function goThere() {
    const place = sync.goThere()
    if (place) await reader?.open(place.chapter, place)
  }

  onMount(() => {
    const onVisibility = () => (document.visibilityState === 'hidden' ? sync.flush() : sync.onVisible())
    const onHide = () => sync.flush()
    document.addEventListener('visibilitychange', onVisibility)
    addEventListener('pagehide', onHide)
    return () => {
      sync.flush()
      document.removeEventListener('visibilitychange', onVisibility)
      removeEventListener('pagehide', onHide)
    }
  })
</script>

<Reader
  bind:this={reader}
  {name}
  {chapter}
  {start}
  onspot={place => sync.report(place)}
  onchapter={() => sync.flush()}
>
  {#if asking}
    <ContinuePrompt theirs={asking.theirs} ours={asking.ours} onchoose={choose} />
  {/if}
  {#if sync.banner}
    <ConflictBanner theirs={sync.banner} ongo={goThere} onkeep={() => sync.keepHere()} />
  {/if}
</Reader>
