---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:85153cb99212557094a9262ac48f3028f1cc9406bece14098fbf796a72df5091'
step_id: 'S77'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Diagnose the two red AEAT-CSV-register cross-period clean-state tests, which were flagged unowned and are now shown to be a real product defect rather than stale expectations. CORRECT AN EARLIER MISREADING FIRST: the direction was recorded backwards. The test EXPECTS MISSING_EXTERNAL_EVIDENCE_RECORD and the code EMITS MISMATCHED_EXTERNAL_EVIDENCE_RECORD, not the reverse. THE SERIOUS HALF IS THE SECOND TEST, and it is the one that changes the severity of this finding. test_cross_period_clean_state_accepts_csv_register_with_matching_justificante_metadata seeds a fully-matching import through the REAL import flow and expects zero blockers; it receives MISMATCHED_EXTERNAL_EVIDENCE_RECORD. That is not a test-expectation problem. import_external_filing_evidence demonstrably writes both keys the checker reads -- external_evidence_reference_id and filing_record_id, alongside source_kind AEAT_CSV_REGISTER -- so a csv-register import that SHOULD satisfy the gate does not. If that reproduces outside the fixture it means a CSV-register-backed prior filing can never satisfy cross-period clean state, which blocks Modelo 390 and every dependent modelo for any operator whose priors were imported through the register. That is a filing-blocking defect, not a cosmetic one. THE FIRST TEST IS A SEPARATE, MILDER DEFECT IN THE SAME BRANCH: with justificante metadata omitted, absent metadata falls straight into the equality comparison and is reported as a mismatch. The receipt-bound branch immediately below already distinguishes these two states correctly -- justificante is None yields MISSING, a non-matching justificante yields MISMATCHED -- so the csv-register branch is simply missing the parallel absent-versus-divergent split its sibling has. The distinction is operator-facing and load-bearing, because these blockers project onto different OperatorActionAxis values: MISSING sends the operator to capture the evidence, MISMATCHED sends them to resolve a divergence, and telling someone to reconcile a divergence when nothing was ever captured is actively wrong guidance. NOT FIXED YET, and deliberately not guessed at. Three candidate causes remain for the accepts case and they are not distinguishable by reading: the persisted observation source_kind may not be AEAT_CSV_REGISTER, the metadata reference may not equal the filing's external evidence reference, or metadata filing_record_id may have gone stale against a filing record replaced after import. The next action is a targeted run that prints the three compared values rather than another round of inference. Both this module's helper and external_import_actions.py were last touched by the same commit 6babb35980, which is the first place to look for what moved

## Scope

- `src/cadrumo/application/calculations/cross_period_clean_state.py`
- `src/cadrumo/application/modelo/external_import_actions.py`
- `src/cadrumo/application/calculations/tests/_cross_period_clean_state_support.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S77.md`

## Notes

- Lifecycle retraction only: S78 supersedes S77's filing-blocking production-defect inference. The real import wrote the CSV-register identity; the S77 fixture then overwrote it, so the red test did not establish a production defect.
- S79 implements the separate fixture and absent-metadata production remedies; S87 later records a plan-level narrow verification statement. Relevant hunk provenance is `2688c6b4e02f5f1b189d6a32c8684c96eadd2b77` and VIGENTE hardening `127964d0b07f85bf2c25a6bc2378e5222000049a`. These are downstream relations only and their peer co-commit paths are excluded.
- S77 made no source action and claims no production defect. There is no recoverable historic literal receipt and no fresh receipt. S87 plan prose is not borrowed as S77 evidence.
