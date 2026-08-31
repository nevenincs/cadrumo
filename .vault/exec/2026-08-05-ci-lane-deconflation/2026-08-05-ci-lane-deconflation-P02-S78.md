---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:1c3857c26494a122afa772964ec408bf830d9821313bbb738839d3de1256477f'
step_id: 'S78'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# CORRECT the severity recorded for the two red AEAT-CSV-register cross-period tests in the sibling Step, which OVERSTATED the defect, and record the actual root cause. The sibling Step reasoned that because the real import flow writes both keys the checker reads, a matching csv-register import failing the gate implied a filing-blocking production defect that would block Modelo 390 for every operator whose priors came through the register. THAT INFERENCE WAS WRONG, and the missing fact was one line further down the fixture. _seed_official_303_source_filings calls import_external_filing_evidence, which correctly persists an observation with source_kind AEAT_CSV_REGISTER plus external_evidence_reference_id and filing_record_id -- and then unconditionally calls _save_source_observation for the same modelo, year and period, which saves over that same observation key with source_kind defaulting to the literal aeat_sede_justificante and a default_source_metadata carrying only aeat_register_status, aeat_expediente_id, authenticated_identity and sometimes aeat_justificante_csv. Neither key the csv-register branch compares survives, and the source kind no longer matches either, so the checker's first equality fails and reports MISMATCHED. THE FIXTURE CLOBBERS WHAT THE PRODUCTION PATH CORRECTLY WROTE. The production csv-register path is therefore NOT shown to be broken, and no claim that it is should stand on this evidence. The lesson is the one this campaign keeps relearning from the other side: a red gate is not proof that production is wrong, and reading one half of a fixture is not reading the fixture. THE MILDER DEFECT IN THE SIBLING STEP STILL STANDS and is unaffected by this correction, because it is about the SHAPE of the branch rather than about what the fixture wrote: with metadata absent the csv-register branch runs straight into an equality comparison and reports a mismatch, where the receipt-bound branch immediately below correctly splits absent from divergent by testing for None first. That split is operator-facing, since MISSING and MISMATCHED project onto different OperatorActionAxis values and sending an operator to reconcile a divergence when nothing was captured is wrong guidance. FIX SHAPE: the seeded observation for a csv-register period must carry source_kind aeat_csv_register and the two metadata keys, with filing_record_id read from the record the import actually created rather than invented, so the fixture stops contradicting the flow it just exercised. Do not resolve it by relaxing the checker's comparison, which is the one thing here that is behaving correctly

## Scope

- `src/cadrumo/application/calculations/tests/_cross_period_clean_state_support.py`
- `src/cadrumo/application/calculations/cross_period_clean_state.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S78.md`: records the S78 correction/lifecycle attestation.
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s78-correction-lifecycle-self-review-audit.md`: records the independent correction-boundary review.
## Notes

This is a correction and lifecycle attestation for the exact plan row at `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md:106`; it made no source action. S78 retracts S77's filing-blocking production-defect inference: the fixture saved an observation over the real CSV-register import's key, replacing its source kind and the two identity values used by the checker. The red accepts case therefore did not establish a broken production import.

S79 owns the fixture and missing-metadata remedies. Commit `2688c6b4e02f5f1b189d6a32c8684c96eadd2b77` is downstream provenance only: its relevant hunk restores the CSV-register fixture identity and distinguishes wholly absent metadata from a divergence. S82 identified the superseded-record selection risk; S87 later records the VIGENTE hardening and a plan-level narrow verification assertion. None of those downstream actions or their verification is claimed as S78 work.

Current source remains consistent with the correction: the CSV-register comparison now lives in `src/cadrumo/application/calculations/_cross_period_external_evidence.py` and distinguishes absent metadata from divergent identity; the fixture preserves CSV-register identity and selects only VIGENTE records in `src/cadrumo/application/calculations/tests/_cross_period_clean_state_support.py`. This is read-only current-branch evidence, not a fresh test result. No historic literal terminal receipt was recovered; S87 plan prose is not borrowed. No fresh run was started because pytest PIDs 70372, 92348, and 114528 were active on the shared worktree.
