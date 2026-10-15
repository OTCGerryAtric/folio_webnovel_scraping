"""Report lines for what cleaning removed. Text vanishing silently is how trust goes."""

from __future__ import annotations

_TYPOGRAPHIC = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "…": "...", "–": "-", "—": "-",
})


def console_safe(text: str) -> str:
    """Typographic punctuation to ASCII; anything else unprintable becomes '?'.

    A Windows console in a legacy code page raises on what it cannot encode.
    """
    return text.translate(_TYPOGRAPHIC).encode("ascii", "replace").decode("ascii")


def report_removals(removals, total: int, report) -> None:
    if not removals:
        return
    report(f"Removed {len(removals)} boilerplate block(s):")
    for removal in removals:
        report(f"  on {removal.pages}/{total} pages: {removal.text}")


def report_trims(trims, report) -> None:
    """Say which pages opened with a recap, and what went with it."""
    if not trims:
        return
    blocks = sum(trim.blocks for trim in trims)
    report(f"Trimmed {blocks} repeated block(s) from the start of {len(trims)} page(s):")
    for trim in trims:
        report(f"  page {trim.number}: {trim.text}")


def warn_if_emptied(pages, report) -> None:
    """An emptied page means the threshold was too aggressive. Say so."""
    emptied = [p.number for p in pages if p.is_empty]
    if emptied:
        report(
            f"warning: {len(emptied)} page(s) were left with no text "
            f"(first: {emptied[0]}). Try --dedupe-threshold with a higher "
            f"value, or --no-dedupe. Re-running costs nothing: the pages "
            f"are cached."
        )
