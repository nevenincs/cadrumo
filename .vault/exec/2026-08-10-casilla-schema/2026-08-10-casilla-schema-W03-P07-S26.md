---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:c6ab036df4aa7cea770ce05c21a92df62c6e33a971c8febb7daf72be3f4b5f13'
step_id: 'S26'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

# register the modelo.work.review envelope wrapping the record, with the spine axis and machine facts riding Notice context

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_payloads.py`

## Description

- Register `modelo.work.review` to a strict `WorkReviewResult` that wraps the facade-exported `ModeloWorkReview` without redeclaring its fields.
- Compose a real review record from encrypted persistence repositories and the bundled registry authority.
- Reuse `verification_report_notices` from the persisted verification report underlying that review.
- Prove schema-registry identity, strict `SchemaEnvelope` JSON roundtrip, warning status, blocker action-axis identity, native code, and matching machine facts in `Notice.context`.
- Run focused pytest, Ruff format and lint, BasedPyright, diff hygiene, the orphan-leaf conformance probe, and the feature-scoped Vault check.

## Outcome

`modelo.work.review` now has one strict result schema whose only domain payload is the canonical application `ModeloWorkReview`. No CLI-side casilla, progress, finding, or blocker mirror was introduced, and no new Notice projection helper was added.

The real-storage envelope test passed. It persists a work unit, calculation revision, and blocking verification report, builds the application review through `build_modelo_work_review`, obtains notices through the existing canonical `verification_report_notices`, and round-trips the result through the parameterised `SchemaEnvelope` JSON contract. A deliberate temporary registration-key mutation made the test fail with a missing `modelo.work.review` registry key, then the canonical registration was restored and the test passed again.

Focused Ruff formatting and lint passed. The new test module passed BasedPyright with zero errors, warnings, or notes. Whole-file BasedPyright over `_modelo_payloads.py` retained four pre-existing diagnostics outside the S26 changes: two around the `WorkAmendResult.amends_filing_record_id` override and two in the `ModeloAggregateResult` source-kind coercion.

## Notes

No live `aeat app modelo work review` command exists in the current Typer tree, and adding one is outside S26 ownership. The exact CLI smoke is therefore not applicable. The symmetric CLI-leaf/schema-registry integration gate reports exactly one orphan key, `modelo.work.review`; later review-surface wiring owns invocation. The S26-focused contract remains green and does not invent a premature facade or shim.

The initial inventory found unrelated peer modifications in `_ledger_evidence_review_cli.py` and `_modelo_discovery_cli.py`. Neither path overlaps S26, and both were preserved untouched. No staging, commit, plan-state mutation, audit authoring, or unrelated cleanup was performed.
