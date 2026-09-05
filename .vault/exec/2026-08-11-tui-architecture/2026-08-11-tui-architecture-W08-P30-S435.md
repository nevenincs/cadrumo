---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:b3d4f3572e8137c987d1fc2810a297cacdb2e912262bfba9c02325b59356df81'
step_id: 'S435'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give the page-resolved M200/2024 casillas their own adjudication cohort and compiler, so the label gate asserts them. The 40 record-qualified casillas grounded in S431 and S432 belong to no existing cohort, so nothing pinned them. Follow the established pattern: a receipt TOML whose every digest the compiler re-derives from the bundled design rather than trusting, refusing a member that does not resolve to exactly one cell on its own page or whose declared section that cell contradicts.

## Scope

- `dev/registry/analysis/m200_2024_page_resolved_adjudications.py`
- `dev/registry/analysis/m200_2024_page_resolved_adjudications.toml`
- `dev/registry/tests/test_m200_2024_page_resolved_adjudications.py`
- `dev/locales/tests/test_casilla_label_matches_pinned_official_text.py`

## Changes

TASK A IS NOW CLOSED. The 40 record-qualified casillas grounded in S431 and S432
belonged to no adjudication cohort, so nothing pinned them. They have one now,
in the established pattern: a receipt TOML beside a compiler that re-derives
every digest from the bundled design at compile time and refuses a recorded
value the design does not produce. The file is a receipt of what was resolved,
never the authority for it.

The cohort's claim is narrower than the other three and needs no adjudicating
judgement: a record-qualified identifier carries its own page, the design is
segmented by page, so the number resolves to exactly one cell. What a page
cannot supply is corroboration, so the compiler also refuses a member whose
declared section does not appear in the resolved cell's path -- casilla 00067 is
the standing proof that a declaration can name a part of the form its own cited
design does not put the number in.

Coverage across all four authorities: 196 pins available, 183 casillas asserted,
up from 143 at the start of this Step and 117 before Task A began.

Teeth on a casilla only this cohort pins: DP200013:00417's label moved from
"Liquidacion II" to "Liquidacion I" -- a real section name from the same
document, one word changed. The gate failed. Restored by copy; 4 passed.

The compiler's own gates carry their teeth inline rather than as a separate
exercise: one edits a recorded digest to prove the receipt is checked rather
than believed, and one injects 00067 to prove the corroboration refuses a
declaration its design cell contradicts.

## Notes

The 13 pins that are available but unasserted belong to casillas still
unlabelled, all inside the 16 that Task C addresses.

Task B is next: 381 ellipsis-truncated Spanish labels, and the 24 Hungarian gaps
sitting behind them.
