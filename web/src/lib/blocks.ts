// What a build will write, worked out in the browser so the build panel can
// preview it. Mirrors build_blocks and build in scraper/stages.py: blocks sit
// on round numbers, empty blocks are skipped, and each file is named after
// the chapters it actually holds.

export interface PlannedFile {
  first: number
  last: number
  name: string
  chapters: number
}

export interface PlanOptions {
  every: number
  start?: number | null
  end?: number | null
  bookName: string
  format: string
}

export function planBuild(cleaned: number[], o: PlanOptions): PlannedFile[] {
  const nums = cleaned
    .filter(n => (o.start == null || n >= o.start) && (o.end == null || n <= o.end))
    .sort((a, b) => a - b)
  if (!nums.length) return []

  const file = (held: number[]): PlannedFile => {
    const first = held[0]
    const last = held[held.length - 1]
    return { first, last, name: `${o.bookName} ${first}-${last}.${o.format.toLowerCase()}`, chapters: held.length }
  }
  if (!o.every) return [file(nums)]

  const blocks = new Map<number, number[]>()
  for (const n of nums) {
    const index = Math.floor((n - 1) / o.every)
    const held = blocks.get(index)
    if (held) held.push(n)
    else blocks.set(index, [n])
  }
  return [...blocks.keys()].sort((a, b) => a - b).map(index => file(blocks.get(index)!))
}
