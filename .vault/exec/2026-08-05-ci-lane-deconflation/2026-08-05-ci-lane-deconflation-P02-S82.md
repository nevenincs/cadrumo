---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:92332a32377902d1f651d9c71456e253e49553d923f7b3167a40ae039b817cd8'
step_id: 'S82'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Harden the csv-register fixture fix against selecting a superseded filing record.

## Scope

- `src/cadrumo/application/calculations/tests/_cross_period_clean_state_support.py`

## Changes

- `M` `src/cadrumo/application/calculations/tests/_cross_period_clean_state_support.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S82.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s82-execution-self-review-audit.md`

## Notes

- S82 owns the latent selection risk: a work unit can retain VIGENTE and SUPERSEDIDO filing records, while the checker resolves the current record. Immutable mixed commit `9bc7c757c2d8101889ac075a443ebd9203d062f1` narrows the fixture candidate to `record.status is ModeloRecordStatus.VIGENTE`; if none exists it leaves `filing_record_id` absent rather than inventing a divergent id.
- S79's `2688c6b4e02f5f1b189d6a32c8684c96eadd2b77` fixture/metadata and absent-versus-divergent remedy is prior work, not this selection mitigation. S87 later ran the narrow provenance module twice with 13 passes after the VIGENTE change; that is downstream verification and is not used as an S82 receipt.
- No literal S82 test command or terminal output is recoverable, and no test was run for this documentation-only reconciliation.
