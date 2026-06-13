---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S04'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
---

# `live-iva-compensation-wallet` `W01.P03.S04`

Hardened the backend operator-approved wallet pull path so it persists, reloads, reconciles, and verifies wallet decisions before returning a report.

- Modified: `src/aeat/application/live/__init__.py`
- Modified: `src/aeat/application/calculations/_observations_repository.py`
- Modified: `src/aeat/application/calculations/test_observations_repository_roundtrip.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py`
- Created: `src/aeat/application/live/test_iva_wallet_capture_backend.py`
- Created: `src/aeat/application/live/test_iva_wallet_live.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The application live wallet path now routes through `persist_and_reconcile_iva_compensation_wallet`. The helper stores the raw wallet observation, reloads it from encrypted evidence storage, reconciles using the reloaded observation, then reloads the persisted reconciliation decision before returning the operator report. This keeps the backend from trusting transient browser memory when the actual calculation chain depends on persisted evidence.

The IVA wallet reconciliation decision key was changed from a cleartext taxpayer-period key to an opaque SHA-256 based key. Existing cleartext keys remain readable as a legacy fallback, but new writes no longer expose the taxpayer NIF/NIE in storage metadata.

The wallet-relevant persistence tests now avoid process environment mutation; they use scoped settings overrides and scoped SQL engine disposal. The application-level live test verifies the profile-driven wallet capture, persisted evidence reload, decision-history load, and local Modelo 303 guard against the live decision when `AEAT_LIVE_TESTS_ENABLED` is set.

The plan row was closed by direct edit because `uv run vault plan step check .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md W01.P03.S04` could not spawn `vault`.

## Tests

`uv run ruff check` passed for the changed wallet, recurrence, live, and repository files.

`uv run pytest src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py src/aeat/application/live/test_iva_wallet_live.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_filed_capture_calculation_history.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_bucket_aggregation_flow.py -q --disable-warnings` completed with 42 passed and 2 live-gated deselected.

`uv run python -m aeat.locales audit` and `uv run python -m aeat.locales scaffold --check` both passed.
