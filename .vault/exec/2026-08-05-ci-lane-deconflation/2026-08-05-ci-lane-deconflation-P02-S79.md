---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7a96232b18d4fbff69b9014f59475b63de4474fd60d1f73619feb0c04a8c81a1'
step_id: 'S79'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Fix both AEAT-CSV-register cross-period defects at their real causes, one in the fixture and one in production, keeping the checker's comparison untouched because it is the component behaving correctly. FIXTURE, closing the accepts case: _seed_official_303_source_filings now reproduces the register identity on the observation it saves over the imported one. For a csv-register period that actually went through the import flow it sets source_kind to ObservationSourceKind.AEAT_CSV_REGISTER, sets external_evidence_reference_id to the same evidence reference the import used, and reads filing_record_id off the record the import genuinely created by matching work_unit_id in the filing catalogue -- read, never invented, so the fixture cannot drift from the flow it just exercised. Only the DEFAULTS are filled: a test supplying an explicit source kind or explicit metadata for that period still wins, and the csv-register defaulting is skipped entirely when a period declares its own source kind, so no existing scenario is silently rewritten. PRODUCTION, closing the blocks case and the defect that survived the severity correction: the csv-register branch ran absent metadata straight into an equality comparison, so a filing whose register record was never captured was reported as MISMATCHED. It now tests for wholly-absent metadata first and reports MISSING_EXTERNAL_EVIDENCE_RECORD, exactly as the receipt-bound branch immediately below already does by testing its justificante for None before comparing it. This is operator-facing rather than cosmetic: the two blockers project onto different OperatorActionAxis values, so the previous behaviour told an operator to reconcile a divergence when there was nothing to reconcile against. The mismatch comparison itself is unchanged and still fires on a wrong source kind, a divergent reference, or a divergent filing record id.

## Scope

- `src/cadrumo/application/calculations/cross_period_clean_state.py`
- `src/cadrumo/application/calculations/tests/_cross_period_clean_state_support.py`

## Changes

- `M` `src/cadrumo/application/calculations/cross_period_clean_state.py`
- `M` `src/cadrumo/application/calculations/tests/_cross_period_clean_state_support.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S79.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s79-execution-self-review-audit.md`

## Notes

- Historical implementation landed in mixed peer commit `2688c6b4e02f5f1b189d6a32c8684c96eadd2b77`; this record attributes only the two S79 hunks above, not the commit's unrelated paths.
- Current code has since moved the production branch to `src/cadrumo/application/calculations/_cross_period_external_evidence.py`; read-only inspection confirms the absent-versus-divergent split remains. No fresh pytest was run or claimed because pytest was active on the shared worktree and no historical terminal receipt is recoverable.
- `9bc7c757c2d` is a downstream VIGENTE-only selection correction; S82 identifies that risk and S87 owns its later plan-level verification assertion. Neither is claimed as S79 work.
