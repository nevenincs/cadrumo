---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:14445f0cdbcb31b524f516da0b872d9f25befc5dab19de09cce611b2f1e152eb'
step_id: 'S24'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Finding-to-casilla attribution sweep

## Scope

Sweep every production `ModeloVerificationFinding` construction site under `src/cadrumo/application/modelo/` that omitted `casilla_id`. Populate the field only where existing typed evidence names one affected target casilla, and preserve genuinely record-level findings as `None`. This execution did not edit the plan, audits, or source outside `application/modelo` and its direct tests.

## Description

The sweep used typed evidence already present at each producer boundary; it did not infer casilla ownership from message prose or coincident identifiers. Constructor sites without one canonical affected target casilla remain deliberately record-level.

## Discovery boundary

The accepted read-model ADR, S24 plan row, S23 execution, and S23 audit were read before implementation. The fresh vault semantic search succeeded for the `casilla-schema` feature. The implementation session's code-index attempt was blocked by active index job `1fabdf9e`; the fallback was whole-file reading plus an exact Python AST census, targeted `rg`, and runtime registry probes. A later closeout code-search re-probe succeeded after that active-job boundary cleared; semantic search remained discovery input rather than census proof.

## Initial construction-site census

The current tree did not match the plan's historical 26-site/18-file estimate. The pre-edit AST census found 25 omitted `casilla_id` keywords across these 9 production files:

- `src/cadrumo/application/modelo/_attribution_received_advisory.py:118,134`
- `src/cadrumo/application/modelo/_ledger_drift_gate.py:132`
- `src/cadrumo/application/modelo/_m210_agrupacion_renta.py:123`
- `src/cadrumo/application/modelo/_m210_rate.py:62`
- `src/cadrumo/application/modelo/_m303_m349_reconcile.py:214`
- `src/cadrumo/application/modelo/_objective_estimation_advisory.py:127`
- `src/cadrumo/application/modelo/_verification_actions.py:359,429,442,1355,1371,1427,1667`
- `src/cadrumo/application/modelo/_verification_cross_period.py:100,364,422,466,493,537,557,584,615`
- `src/cadrumo/application/modelo/_verification_predicates.py:790,800`

Across the complete production surface, that was 33 constructors in 16 files: 8 populated and 25 omitted. These are measurements of the inspected revision, not test invariants or expected-count gates.

## Attributable findings

Six construction sites gained or now provide target-casilla attribution:

- The two M100 attribution-received advisories use the semantic-role-resolved local `casilla_id`. Their source change landed independently during the shared-worktree session as commit `3612ed5d74` (`fix(modelo): populate casilla_id on attribution-received advisory findings`); this execution retained direct assertions for both paths.
- The M210 unavailable-rate builder accepts an optional typed `CasillaId`; the unresolved-outcome consumer supplies the exact persisted `RegistryCalculationUnresolvedOutcome.casilla_id`. Direct scalar rate-resolution calls remain record-level because they do not own a formula target.
- The IVA-wallet verification finding names the public canonical `M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA` rather than restating printed box 110.
- Both registry-predicate construction sites parse the existing expression and attribute only when it names exactly one casilla. Multi-casilla and zero-casilla predicates remain record-level.

## Record-level adjudication

Nineteen construction sites remain without `casilla_id` for specific semantic reasons:

- Ledger snapshot drift covers the stored draft's contributing ledger as a whole.
- M210 grouped-renta validation covers the annual detail-row set, not one scalar box.
- M303/M349 reconciliation compares three casillas across two modelos and has no single affected target casilla.
- Objective-estimation exclusion compares profile facts with legal thresholds, not a filing box.
- Cuota-less ledger-row substrate and both missing-evidence findings are transaction-grain; their durable transaction diagnostics do not carry a canonical target casilla.
- OSS missing/unrouted evidence spans multiple OSS bindings; the persisted source issue carries neither binding nor casilla identity.
- Registry snapshot resolution failure occurs before a revision casilla can be named.

All nine `_verification_cross_period.py` sites remain record-level:

1. `_modelo_202_incomplete_modality_finding` is a profile-derived filing-modality failure, not a box failure.
2. `_cross_period_clean_state_findings` emits one finding per dependency, but the requirement stores upstream `source_casilla_ids` and target binding/relation `origin_ids`, not one canonical target casilla. Formula-only and multi-consumer channels exist, so an upstream identifier must not be attached to a target review row.
3. `_cross_period_operator_declared_suppression_advisory_finding` concerns operator-declared activity-start provenance for a suppressed dependency.
4. `_cross_period_first_year_fractional_suppression_advisory_finding` concerns first-year filing obligation and M202 modality.
5. `_cross_period_missing_activity_start_finding` concerns an absent profile fact at target-record grain.
6. `_cross_period_modelo_not_applicable_advisory_finding` summarizes one or more inapplicable source modelos.
7. `_cross_period_zero_value_previous_filing_advisory_finding` concerns dependency suppression evidence; its source boxes are upstream and its origin does not guarantee one target casilla.
8. `_cross_period_m111_no_retenciones_advisory_finding` concerns profile-backed no-obligation evidence for a source period.
9. `_cross_period_non_official_local_chain_advisory_finding` concerns the provenance of an admitted local filing chain.

This preserves the read model's target-row equality contract and avoids introducing a second inverse relation/formula mapper outside the canonical registry homes.

## Files

Source changed for S24:

- `src/cadrumo/application/modelo/_m210_rate.py`
- `src/cadrumo/application/modelo/_verification_actions.py`
- `src/cadrumo/application/modelo/_verification_predicates.py`
- `src/cadrumo/application/modelo/_attribution_received_advisory.py` via external shared-tree commit `3612ed5d74`

Direct tests changed:

- `src/cadrumo/application/modelo/tests/test_actions.py`
- `src/cadrumo/application/modelo/tests/test_attribution_received_advisory.py`
- `src/cadrumo/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py`
- `src/cadrumo/application/modelo/tests/test_verification_m131_indices_generales_incompatibility_advisory.py`

## Verification

Exact focused behavior command:

```powershell
uv run pytest -q -n0 src/cadrumo/application/modelo/tests/test_attribution_received_advisory.py src/cadrumo/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py src/cadrumo/application/modelo/tests/test_verification_m131_indices_generales_incompatibility_advisory.py src/cadrumo/application/modelo/tests/test_actions.py::test_cross_casilla_invariant_finding_is_locale_neutral src/cadrumo/application/modelo/tests/test_actions.py::test_iva_wallet_blocked_exception_carries_translated_message_key src/cadrumo/application/modelo/tests/test_modelo_work_review.py
```

Result: 39 passed in 29.99 seconds.

Additional gates:

- Scoped Ruff over all S24 source and direct-test files: passed.
- Scoped BasedPyright over all S24 source and direct-test files: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed; PowerShell reported only existing CRLF-to-LF notices on files it inspected.
- Final exact AST census: 33 constructors across 16 production files, 14 with an explicit `casilla_id` keyword and 19 without. This is a recorded fixed-point measurement, never an exact-count pass condition.
- The S24 precondition campaign module produced 6 passed and 1 unrelated failure: the current shared tree lacks the English locale entry `application.modelo.findings.foreign_asset_redeclaration` for `application/calculations/_foreign_asset_redeclaration.py`. It is outside S24 ownership and was not modified.
- A broader `test_actions.py` run produced 71 passed and 1 unrelated existing failure: M100 revision replay lacked binding `renta-2024-profile-deduccion-maternidad`. The exact S24 selectors from that module passed.

## Notes

The counts in this record are inspection measurements only. The implementation and tests gate attribution semantics, not a frozen constructor tally.

## Outcome

S24 reached a semantic fixed point: every construction site with existing evidence for one affected target casilla now carries it, and every remaining omission is deliberately record-level with its reason recorded above. No fake, stub, mock, patch, monkeypatch, skip, xfail, mirrored business logic, or exact-count gate was introduced. No plan checkbox, source staging, or commit was performed by this execution-record step.

