---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:31d016b28cad29c1eb5370150766517cbb990a5b126205d82a79ecb7f209cd62'
step_id: 'S31'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---
# `declaracion-real-render-verification` execution: `P04.S31`

## Description

- Correct the provisional Modelo 202 declaration-PDF profile to declare `confidence = "review_required"` and `corpus_round_trip_verified = false`.
- Add a registry-build invariant that rejects a provisional `declaracion_pdf` profile which claims strict confidence or corpus round-trip proof.
- Apply that invariant before the optional specimen-corpus gates, so the contradiction cannot be hidden when no authoring corpus is supplied.
- Keep the Modelo 202 profile visible in the loaded snapshot and retain D5 non-enrolment in the public `modelo_reconcile` path.
- Add a committed-Modelo-202 mutation proof and assert the corrected evidence state at the parser snapshot boundary.
- Add a direct M202 public-runtime refusal proof that uses the committed declaration fixture and fails if M202 is added to the reconcile enrolment set.
- Update the existing provisional-gate test helpers so their provisional fixtures use the coherent review-required, non-round-trip evidence state.

## Outcome

The specimen-less Modelo 202 profile now truthfully exposes its provisional evidence state while remaining available to declaration parsing. Registry validation rejects both contradictory claims at build time, before an installation can create a snapshot with an ungrounded strict or round-trip assertion. The public reconcile boundary still refuses M202 declaration evidence before parsing, so D5 non-enrolment is an executable contract rather than an untested selector membership fact.

## Verification

`uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_m202_provisional_profile_evidence.py src/cadrumo/adapters/inbound/declaracion/tests/test_parser_boundary_m202.py -n 0 -q`

`6 passed in 16.79s`

`uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_m202_provisional_profile_evidence.py src/cadrumo/adapters/inbound/declaracion/tests/test_parser_boundary_m202.py src/cadrumo/domain/calculations/registry/tests/test_corpus_round_trip_gate.py src/cadrumo/domain/calculations/registry/tests/test_provisional_specimen_gate.py -n 0 -q`

`28 passed in 13.07s`

`uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_provisional_specimen_gate.py src/cadrumo/domain/calculations/registry/tests/test_corpus_round_trip_gate.py src/cadrumo/adapters/inbound/declaracion/tests/test_parser_boundary_m202.py src/cadrumo/application/modelo/tests/test_reconcile_declaracion_casillas_multi_modelo.py`

`34 passed in 20.97s`

`uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_modelo_202_registry.py src/cadrumo/domain/calculations/registry/tests/test_every_computed_casilla_enrolled.py`

`11 passed in 12.40s`

`uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_reconcile.py::test_modelo_reconcile_refuses_modelo_202_declaration_before_parsing src/cadrumo/domain/calculations/registry/tests/test_m202_provisional_profile_evidence.py src/cadrumo/adapters/inbound/declaracion/tests/test_parser_boundary_m202.py -n 0`

`7 passed in 9.35s`

`uv run --no-sync basedpyright src/cadrumo/domain/calculations/registry/_validate_extraction_profiles.py src/cadrumo/domain/calculations/registry/_validate_record_sections.py src/cadrumo/domain/calculations/registry/tests/test_m202_provisional_profile_evidence.py src/cadrumo/domain/calculations/registry/tests/test_corpus_round_trip_gate.py src/cadrumo/domain/calculations/registry/tests/test_provisional_specimen_gate.py src/cadrumo/adapters/inbound/declaracion/tests/test_parser_boundary_m202.py src/cadrumo/application/modelo/tests/test_reconcile.py`

`0 errors, 0 warnings, 0 notes`

The committed-Modelo-202 mutation proof changes each otherwise-valid profile claim in turn and confirms that `RegistryValidator.validate_modelo` raises `RegistryValidationError`; the untouched corrected profile validates cleanly. The public M202 reconcile proof uses the committed declaration fixture and expects `ReconciliationDeclaracionSourceUnsupportedError`, so enrolling M202 changes the result and makes the test fail.

## Notes

A discarded broad filename sweep of all declaration parser-boundary tests collected 81 tests and produced 79 passes with two failures in Modelo 390 expected-casilla assertions. No Modelo 390 file belongs to this Step's payload, and the cause of those failures was not attributed during this Step.
