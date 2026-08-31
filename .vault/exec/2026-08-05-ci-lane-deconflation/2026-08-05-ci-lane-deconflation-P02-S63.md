---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:6bdff8f40515893b676a916f83cb95b72b5a54860e7d94c9bb96b876705a7936'
step_id: 'S63'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Execute the accepted narrow-mechanism-widening ADR and correct the join ratchet's own overstatement. DONE 2026-08-28; plan `2026-08-28-registry-narrow-mechanism-widening-plan` is 6/6. Three deliberately narrow registry mechanisms were widened by explicit declaration rather than by relaxing a matcher, and each widening carries a both-directions gate. WHAT LANDED: a `DESIGN_CONSTANT` binding source kind closing M720's live blank-emission path; a `RecordDesignRangeStartCorrection` kind with its precondition enforced at EXTRACTION, closing the last of 218 bundled designs (worklist 9 unread -> 0, confirmed corpus-wide); and an auxiliary-header contract that stopped asserting the filing CADENCE of whichever modelo carries it, which admitted Modelo 131's page zero across four revisions -- a beneficiary nobody predicted, found by measuring what the change did rather than what it was for. 16 admission gates hold all three from both directions: every declared set must be NON-EMPTY, every range-start correction is proved actually APPLIED, every design constant is proved to FILL its run against the compiled authority, and the unpinned cadence slot is proved to still REFUSE tag constants, footnote markers and BLANCOS with an anti-vacuity half proving it still accepts every cadence AEAT prints. THE LARGER CORRECTION IS TO THE RATCHET ITSELF, and it is the honest headline: of the 25 entries it originally pinned, only 2 were a real defect (M720, fixed) and 12 WERE NEVER DEBT. The inventory was built from `_join_record(...) is None` without enumerating the branches where the join is DELIBERATELY not attempted, and it over-reported three separate populations in turn -- auxiliary envelope headers, sheets whose constants ride on bindings, and declared filing envelopes. M303's five DP30300 entries were the largest: DP30300 is a correctly-classified VARIABLE envelope and the layout's declared filing_envelope, so coverage answers it from the envelope contract, deliberately skipping a join that would otherwise match a page at unrelated offsets. Ratchet 25 -> 11, and every one of the 11 survivors was then individually verified to have no filing envelope, no aux header and no variable envelope -- so the join really was attempted and really did fail. The number moved mostly by removing false claims about the codebase, which is the opposite of what a shrinking metric usually implies

## Scope

- `src/cadrumo/core/aggregation.py`
- `src/cadrumo/domain/calculations/registry and the join ratchet gate`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S63.md`
- `verify:` `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_narrow_mechanism_admissions.py src/cadrumo/domain/calculations/registry/tests/test_every_bundled_design_is_read_or_reported.py src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py` -> `pass` (26 passed, 2 openpyxl conditional-formatting warnings, 363.60s)
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/aggregation.py src/cadrumo/application/modelo/calculation_route.py src/cadrumo/domain/calculations/registry/bindings.py src/cadrumo/domain/calculations/registry/design_constant_bindings.py src/cadrumo/domain/calculations/registry/record_design.py src/cadrumo/domain/calculations/registry/record_design_schema.py src/cadrumo/domain/calculations/registry/_validate_export_layout_coverage.py src/cadrumo/domain/calculations/registry/tests/test_narrow_mechanism_admissions.py src/cadrumo/domain/calculations/registry/tests/test_every_bundled_design_is_read_or_reported.py src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py` -> `pass`

## Notes

- Historical roll-up: `004898c8fa1dee0aaabdcf099ee4255770a0339f` introduces the declared M165 range-start correction and the auxiliary-header cadence admission; `ce7ed9c74ef76a656170e5c8060e4b68fa510779` introduces the design-constant source kind and its binding-aware coverage join. Their historical command output is not preserved. The fresh verification above is contemporary whole-rollup evidence and is not a restatement of the dedicated M720 or later ratchet-reconciliation execution records.

