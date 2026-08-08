---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:0a28674a35c8c87ba0a341788bf1b11285ec45e32d9e2b7972a49d0e1d165bd4'
step_id: 'S05'
related:
  - "[[2026-08-08-m200-export-envelope-tag-plan]]"
---

# confirm the byte-level test goes green for both the open tag and the close tag

## Scope

- `src/cadrumo/application/filing/tests/test_export.py`

## Description

- Re-run the byte-level assertion authored before the restructuring, unchanged,
  against the restructured declaration.
- Re-run the wider Modelo 200 export selection so the neighbouring assertions on
  the same layout — the cuota diferencial slot and the grupo mercantil parent-TIN
  slot that must stay blank — are shown to survive the record's rewrite.

## Outcome

The assertion passes at both ends of the fichero: the first 17 bytes equal
`<T200020240A0000>` and the final 18 equal `</T200020240A0000>`, the two AUX
markers render, and the two EEDD header slots carry the values the export headers
supply. The same test that reported the defect now reports the fix, so nothing
about the expectation was adjusted to fit the output.

The three sibling Modelo 200 export assertions stay green, which matters because
the restructured record sits at the head of the file and every later record's byte
position is measured from it.

## Verification

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export.py -k "modelo_200" -n0 -q
    4 passed, 42 deselected in 18.08s

## Notes
