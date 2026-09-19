---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:5c628a8138bcb1b8ffd708e7f3705bfd20fab2ce011682c2260d3886b4e6e3f2'
step_id: 'S24'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate adjudicated modelo work and verification predicates to typed verdicts

## Scope

- `src/cadrumo/application/modelo`

## Description

- Introduce the canonical `ModeloPreconditionFailure` registry and builders for the adjudicated calculate, verify, and file condition identities.
- Replace verification-finding message and recovery prose with locale-neutral `message_locale_key` and strict typed `message_facts`, while pairing blocking findings with exact typed precondition failures.
- Resolve recovery only through the operator action catalogue and live input schemas; retain explicit no-recovery outcomes for conditions without an executable operator action.
- Render finding messages only at the CLI boundary and render recovery from the paired typed verdict without prose parsing, kind inference, command reconstruction, or an English fallback.
- Remove the dead IVA-wallet finding and localized application helper that duplicated recovery authority.
- Reconcile canonical homes with calibrated `vaultspec-rag` searches followed by exact `rg` and AST checks for schema definitions, constructors, producers, consumers, locale keys, and action projections.
- Add drift-sensitive coverage for all adjudicated disposition groups, profile uniqueness, live schema resolution, locale neutrality, catalogue completeness, blocking-finding totality, and absence of parallel action or localization authority.
- Update production contracts in `src/cadrumo/domain/modelos/_verification_report.py`; `src/cadrumo/application/modelo/__init__.py`; `src/cadrumo/application/modelo/_action_errors.py`; `src/cadrumo/application/modelo/_amendment_actions.py`; `src/cadrumo/application/modelo/_art20_advisory.py`; `src/cadrumo/application/modelo/_art52_advisory.py`; `src/cadrumo/application/modelo/_attribution_received_advisory.py`; `src/cadrumo/application/modelo/_autonomic_deduccion_advisory.py`; `src/cadrumo/application/modelo/_calculation_actions.py`; `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`; `src/cadrumo/application/modelo/_calculation_preparation.py`; `src/cadrumo/application/modelo/_dt12_advisory.py`; `src/cadrumo/application/modelo/_dt12_antiquity_advisory.py`; `src/cadrumo/application/modelo/_filing_actions.py`; `src/cadrumo/application/modelo/_iva_wallet_gate.py`; `src/cadrumo/application/modelo/_ledger_drift_gate.py`; `src/cadrumo/application/modelo/_m210_agrupacion_renta.py`; `src/cadrumo/application/modelo/_m210_convenio_lob_advisory.py`; `src/cadrumo/application/modelo/_m210_rate.py`; `src/cadrumo/application/modelo/_m303_m349_reconcile.py`; `src/cadrumo/application/modelo/_m349_ledger_guard.py`; `src/cadrumo/application/modelo/_objective_estimation_advisory.py`; `src/cadrumo/application/modelo/_preconditions.py`; `src/cadrumo/application/modelo/_pulled_filing_reconcile.py`; `src/cadrumo/application/modelo/_verification_actions.py`; `src/cadrumo/application/modelo/_verification_cross_period.py`; `src/cadrumo/application/modelo/_verification_preconditions.py`; and `src/cadrumo/application/modelo/_verification_predicates.py`.
- Update the rendering and locale boundary in `src/cadrumo/entrypoints/cli/_modelo_rendering.py`; `src/cadrumo/locales/en.yml`; `src/cadrumo/locales/es.yml`; `src/cadrumo/locales/ca.yml`; and `src/cadrumo/locales/hu.yml`.
- Update verification report, renderer, producer, workflow, and migration tests under `src/cadrumo/domain/modelos/tests`; `src/cadrumo/entrypoints/cli/tests`; and `src/cadrumo/application/modelo/tests`, including the dedicated `test_s24_precondition_campaign.py` ratchet.

## Outcome

- Calibrated semantic searches for modelo finding localization, precondition verdict recovery, duplicate fallback guidance, and operator action resolution converged on one authority cluster: `_verification_report.py`, `_preconditions.py`, `_verification_preconditions.py`, `_verification_actions.py`, `_verification_cross_period.py`, `_modelo_rendering.py`, and the operator catalogue and resolver.
- Exact AST reconciliation found one `ModeloPreconditionFailure`, one `VerificationFindingPreconditionProjection`, one `ModeloVerificationFinding`, 33 live production finding constructors, and 67 unique precondition profiles. It found no stale `finding.message`, legacy finding action field, application-layer `tr` call, or locale-key and placeholder issue across English, Spanish, Catalan, and Hungarian.
- `uv run --no-sync pytest -q -m "unit or integration" src/cadrumo/application/modelo/tests/test_s24_precondition_campaign.py` passed 7 tests.
- Focused verification renderer, report round-trip, and precondition tests passed 36 tests; the added real four-locale renderer test passed in the renderer file's 6-test run.
- The canonical missing-casilla consumer correction passed its direct test and 4 proportional provenance tests.
- `uv run --no-sync python -m compileall -q src/cadrumo/application/modelo src/cadrumo/domain/modelos src/cadrumo/entrypoints/cli/_modelo_rendering.py` passed.
- Targeted Ruff checks and format checks passed. Targeted Basedpyright checks over the schema, precondition records, producers, S24 ratchet, and formatted cross-period module reported 0 errors and 0 warnings.
- The independent Terra xhigh review returned code PASS after the HIGH stale test-consumer call and MEDIUM mixed-line-ending finding were remediated without widening production APIs. The formatted cross-period module retained the identical semantic AST hash `ec9f9dfdfbf8a133f42efe3cdbf4e1a184c7607675d0eb96e8422ba8251a4857`.
- Lifecycle prerequisites are satisfied: the CLI reports S24 as the next open Step, `exec_missing_ids` is empty, and S25, S26, and S27 are downstream projection and journey Steps rather than prerequisites for the S24 application contract.

## Notes

- A 22-file expanded affected suite produced 121 passes and 76 failures because concurrent Modelo 303 registry revision and relation work made the shared registry authority invalid before those scenarios reached S24 behavior. Those failures are external to this Step and are not represented as S24 passes.
- Concurrent locale work remains present in the shared worktree. S24 proves only its four supported finding catalogues, placeholders, and runtime selection; it does not claim the unrelated locale worktree surface is globally clean.
- A proportional cross-period run produced 19 passes and 1 external failure because the existing `AEAT-2T` `Justificante.csv` fixture has seven characters while the concurrently hardened schema requires at least eight. The fixture and schema were not changed by S24.
- No compatibility shim, English action fallback, mock, fake, stub, patch, monkeypatch, skip, or xfail was introduced.
