---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S01'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Merge filing-periods.md into filing-calendar.md as a period-tokens-and-dates subsection

## Scope

- `sweep inbound links`
- `delete the merged page`
- `docs/how-to/filing-calendar.md docs/how-to/filing-periods.md`

## Description

- Add the "This page covers the ..." opening paragraph to
  `docs/how-to/filing-calendar.md` per the ADR document convention.
- Replace the thin "When is year-end, and how long are periods?" section with
  a full "Period tokens and dates" section absorbing the whole of
  `docs/how-to/filing-periods.md`: the token list, modelo-specific token
  acceptance, the year/period grammar, the ledger `--filter` clause pair, and
  the year-end note. Duplicated calendar-window prose dropped rather than
  copied.
- Sweep all seven inbound references (`explanation/from-records-to-figures.md`,
  `how-to/filing-readiness.md`, `how-to/index.md` grid card and toctree,
  `how-to/modelo-303.md`, `how-to/modelo-390.md`, `how-to/troubleshooting.md`)
  to the new `filing-calendar.md#period-tokens-and-dates` anchor; the index
  grid card for Filing Periods removed and its promise folded into the Filing
  Calendar card.
- Delete `docs/how-to/filing-periods.md` via `git rm`.

## Outcome

Two thin pages answering one question are now one page. Grep confirms zero
remaining `filing-periods` references outside build artifacts. Net how-to page
count reduced by one, per the condense mandate.

## Notes

Sphinx and conformance gates run at P05.S16 for the whole campaign rather than
per-step; the link sweep here was grep-verified.
