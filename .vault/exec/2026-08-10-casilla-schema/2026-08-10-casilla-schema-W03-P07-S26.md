---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:5619d1681d495f5e773c64f4f8cc66ea8b6368164611fca0ced74b3b8723d2ab'
step_id: 'S26'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

# register the modelo.work.review envelope wrapping the record, with the spine axis and machine facts riding Notice context

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_work_review_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo.py`
- `src/cadrumo/entrypoints/cli/_modelo_rendering.py`
- `src/cadrumo/entrypoints/cli/tests/test_modelo_work_review_envelope.py`
- `src/cadrumo/locales/{en,es,ca,hu}.yml`

## Description

- Register `modelo.work.review` to a strict `WorkReviewResult` that wraps the facade-exported `ModeloWorkReview` without redeclaring its fields.
- Compose a real review record from encrypted persistence repositories and the bundled registry authority.
- Register the smallest read-only `aeat app modelo work review` leaf and call canonical `build_modelo_work_review` against the existing repositories.
- Factor the existing Notice projection into `verification_findings_notices`, keep `verification_report_notices` as its report wrapper, and project the review's own findings without a second repository lookup.
- Prove schema-registry identity, strict `SchemaEnvelope` JSON roundtrip, warning status, blocker action-axis identity, native code, and matching machine facts in `Notice.context`.
- Run the exact stored-review CLI path, focused pytest, Ruff format and lint, BasedPyright, diff hygiene, symmetric CLI-leaf/schema conformance, and the feature-scoped Vault check.

## Outcome

`modelo.work.review` now has one strict result schema whose only domain payload is the canonical application `ModeloWorkReview`, plus a live read-only `aeat app modelo work review` leaf. No CLI-side casilla, progress, finding, or blocker mirror was introduced.

The real-storage envelope tests passed. They persist a work unit, calculation revision, and blocking verification report, build the application review through `build_modelo_work_review`, and round-trip the result through the parameterised `SchemaEnvelope` JSON contract. The exact CLI test invokes `app modelo work review` against that live stored review and proves the blocker axis/native facts and matching `Notice.context`. The command projects `review.findings` through the factored canonical helper, so there is no second verification-repository query. A deliberate temporary registration-key mutation made the contract test fail with a missing `modelo.work.review` registry key, then the canonical registration was restored and the test passed again.

Focused Ruff formatting and lint passed. BasedPyright over the new registrar and direct test passed with zero errors, warnings, or notes. The direct review module passed with two tests, and the exact symmetric integration node `test_every_cli_leaf_has_a_registered_schema` passed. Whole-file BasedPyright over `_modelo_payloads.py` retained four pre-existing diagnostics outside the S26 changes: two around the `WorkAmendResult.amends_filing_record_id` override and two in the `ModeloAggregateResult` source-kind coercion.

## Notes

The live command uses the existing target resolver and repository-backed application producer; it adds no facade, shim, or duplicate review assembly. `cli.app.modelo.work.review_help` was added through `dev.locales` in all four locale catalogs. The locale scaffold check retained unrelated existing drift outside this key.

The initial inventory found unrelated peer modifications in `_ledger_evidence_review_cli.py`, `_modelo_discovery_cli.py`, and the locale catalogs. A transient peer-owned syntax error in `_ledger_evidence_cli.py` initially blocked the conformance node; it cleared without S26 edits and the exact node then passed. All peer changes were preserved. No staging, commit, plan-state mutation, audit authoring, or unrelated cleanup was performed.

History/atomicity note: S26 landed across four commits: the payload and original envelope test were accidentally swept into unrelated refactor a8eb0cd936; the initial execution record landed separately in 278215f04e; its wording was refined in 8db25cff0a; and the reopened command, rendering-helper factor, locale leaf, and direct CLI test landed in 9d416e9006 mixed with the S89 config/ledger translation sweep. This violated the one-Step/one-atomic-commit rule. History was not rewritten. Final closure is audit, plan, and execution-record correction only.
