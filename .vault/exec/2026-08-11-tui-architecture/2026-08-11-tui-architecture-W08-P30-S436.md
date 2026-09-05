---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:b75ab4d0dd85bc9db1841ec84c641cf12b5655a99cc009f9cdbaab348b5291b6'
step_id: 'S436'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Repair the 412 ellipsis-truncated M200/2024 labels from the design their declarations actually cite, and gate the defect class. The truncated casillas cite aeat-dr-200-2025, not the 2024 design every other cohort resolves against, so repairing from 2024 would have silently reauthored 412 filing-bound labels while looking correct. Resolve each against the 2025 design by the exact prefix the truncated label still carries, corroborate against the declared section, then translate the recovered tails and close the Hungarian gaps that sat behind them.

## Scope

- `src/cadrumo/locales/*/modelo/schema/200.yml`
- `dev/locales/tests/test_casilla_labels_are_not_truncated.py`

## Changes

TASK B IS CLOSED. Truncated labels: 412 -> 0 in every locale. Unlabelled
casillas: es and en 16, ca 16, hu 40 -> 16. All four now sit exactly on the 16
that Task C addresses.

THE REPAIR NEARLY USED THE WRONG DESIGN. The plan said to re-derive with the
page selector validated in S432, which resolves against aeat-dr-200-2024. Those
412 casillas cite aeat-dr-200-2025. Resolving them from the 2024 design produced
a cell for all 412 and continued the shipped stem for 376 of them, so it would
have looked right; the 36 that diverged are what exposed it. Casilla 00077 ships
"(DA 18a LIS RDL 5/2023 y RDL 7/2026)" while the 2024 design reads
"(DA 18a LIS RDL 5/2023)", and 00091 ships "ano 2024" against the design's
"ano 2024(*)". Those are two record designs disagreeing, not a selector missing.
Repairing from 2024 would have silently reauthored 412 filing-bound labels to a
design their declarations do not cite.

Against the 2025 design the resolution needs no selector at all. A truncated
label still carries an exact prefix of up to ~180 characters, so the cell that
continues it is identified by the stem itself: 412 of 412 resolved to exactly
one candidate, and 412 of 412 corroborated against their declared section.

The tails are where these labels earn their identity. The design names a box by
a hierarchical path, so two boxes agree for a hundred characters and differ only
at the end -- an increase from a decrease, one year from the next. Cutting the
tail removes the part that says which box it is, which is why this was a
correctness defect rather than an untidiness.

68 new segments were authored for the recovered tails; 140 came from the mined
glossary. Composing the three translations closed the 24 Hungarian gaps in the
same pass, because those were the casillas whose Spanish source had been
truncated -- there had been nothing coherent to translate, and now there is.

New gate: no shipped casilla label contains an ellipsis, per locale. It asserts
the absence only, and says nothing about whether a label is the RIGHT text --
that is the pinned gate's job, and they stay separate because a label can be
complete and wrong or truncated and otherwise correct. Teeth: 00077 re-truncated
at 96 characters; the es case failed and the other three passed, which is the
per-locale parametrisation doing its job. Restored by copy; 5 passed.

## Notes

The runtime localization gate now fails ONLY on the 16 Task C casillas, down
from 644 failures when this work began.

The translation honesty gate's failures are unchanged and none is a casilla
label: ca 16, es 15, hu 9 keys identical to English under tui.aeat_sync.* and
tui.home.*, exactly the counts measured before any of this started.
