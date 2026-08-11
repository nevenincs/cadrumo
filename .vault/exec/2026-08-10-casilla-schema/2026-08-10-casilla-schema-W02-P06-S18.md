---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:88dbd9afbe8e1213fc10382f3c544b46d6e6615e137a4f5e7d5135a1bcc27451'
step_id: 'S18'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Project verification and readiness blockers onto operator action classes

## Scope

- `src/cadrumo/domain/modelos/_verification_report.py`
- `src/cadrumo/domain/modelos/__init__.py`
- `src/cadrumo/application/state_projection.py`
- `src/cadrumo/application/_state_projection_readiness.py`
- `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py`
- Direct verification, readiness, and quickfile contract tests

## Description

- Add a total import-asserted `OperatorActionAxis` projection beside every native `ModeloVerificationFindingKind`.
- Project the readiness payload's `missing`, `missing_bindings`, and `ledger_issues` rows without replacing their native codes or source identities.
- Keep binding sources typed as `BindingSourceKind`, refuse unknown persisted tokens, and map each source to the workflow that can actually satisfy it.

## Outcome

- Verification findings and all three readiness lists carry typed action axes while retaining their native facts.
- The six non-ledger sources resolve truthfully: retenciones, withholding, and foreign assets require supplied observations; atribuciÃ³n members require profile facts; related-party and refund rows require external evidence.
- Focused validation passed: 29 tests, Ruff, strict BasedPyright with zero diagnostics, and diff-check.
- Formal review initially found one MEDIUM semantic mismatch, then independently re-grounded the correction and returned PASS.

## Notes

- Production and primary tests landed in `40ae8e6866` (`feat(modelo): project operator actions onto verification findings and readiness gaps`). That concurrent commit also included an already-present producer-snapshot test hunk, so this record names the actual non-atomic landing rather than rewriting shared history.
- The strict quickfile fixture correction and lifecycle artifacts land in the follow-up closure commit; no compatibility parser or source alias was added.
- Import-time bite proofs removed one verification row and one ledger-issue row in turn; clean imports failed naming the exact missing enum member, then each row was restored before final gates.
- A broader integration selection remains red only on unrelated profile fixtures missing the newly required `tax_residence.jurisdiction_scope`; the exact quickfile strict-source node passes.
