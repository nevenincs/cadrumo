---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:3ad4bab5a526f5c82d3f41ebe648c0e6639d28cc66fbe16ce410f5d46bdc8743'
step_id: 'S413'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Let every workspace table use the width it is given instead of truncating inside it. OPERATOR REVIEW OF THE RENDERED FRAMES, 2026-09-04, generalising what was first measured on one surface: column and row tables across the workbench do not stretch and do not use the screen efficiently. Measured on aeat-sync-filed-declarations at 120x40: the navigation table clips its own header to 'Disponibilid', cuts area names mid-word to 'Declaraciones pr' and 'Comparacion de e', and severs every Fuentes cell at 37 characters, while the painted rows stop near column 78 of 120 and the remaining third of the terminal is blank. NO EXISTING GATE CAN SEE THIS: the responsive suite asserts that nothing crosses the right edge, and nothing does -- truncation inside a table with room to spare paints exactly like a table that fits. Whatever fix lands needs a proof that reads the painted cells for a clipped value beside unused width, in the same shape as the Home column-gutter gate.

## Scope

- `every table-bearing screen under src/cadrumo/entrypoints/tui/ and src/cadrumo/entrypoints/tui/tests/test_workbench_responsive.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/components/widgets.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_workbench_responsive.py`
- `verify:` `pytest -n0 -m '' test_workbench_responsive.py aeat_sync/tests` -> `pass` (84)

## Notes

`ContentDataTable` sized columns from constants authored before anyone saw the
data, and the guess was wrong in the direction that costs the operator
information: `Declaraciones presentadas` clipped to `Declaraciones pr` at width
16, `Modelo 130 · 2026 · 1T` to `Modelo 130 · 202`, each beside a row with
spare width.

Columns are now sized to their own content. The short columns are made whole
and the FILL column yields, rather than every column growing together. Growing
together was tried first and fails exactly where it is needed: one wide
free-text column (`Fuentes`, carrying full source sentences) pushes the natural
total past the terminal, so nothing grows at all and a two-character shortfall
elsewhere goes unfixed. Yielding is also the right way round -- a truncated
identifier or state word is unrecoverable, while the fill column is prose the
operator can open the row to read. The fill column's own header is the floor:
below that it stops naming itself, so the pass stands down entirely.

The gate reads the painted frame and keys on the ellipsis Textual writes when
it shortens a cell, deliberately NOT recomputing the sizing policy -- a test
that recomputed it would agree with any bug the policy contained. It requires a
trailing margin before failing, because at narrow sizes a table legitimately
fills its row and shortening is then correct rather than a misallocation.

This defect was invisible to every existing gate, which is why it survived in a
green suite: the sibling header gate checks headers, not values, and the
overflow gates pass because nothing crosses the right edge. A shortened value
beside an empty margin paints exactly like a value that fits. Teeth proven by
removing the value-driven pass; the gate names the surface and the offending
painted lines. Restored by copy.
