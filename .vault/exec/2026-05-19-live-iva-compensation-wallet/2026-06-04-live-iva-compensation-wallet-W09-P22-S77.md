---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S77'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# `live-iva-compensation-wallet` `W09.P22.S77`

## Scope

Focused validation and review closeout for the live-wallet parser, centralized constants, backend capture/reload, Modelo lifecycle gates, Modelo 303 wallet authority paths, and registry drift fixes.

## Description

- Re-ran the focused wallet/parser/backend/modelo lifecycle gate after S82 live read-only verification and S83 local wallet-only file lifecycle coverage.
- Investigated the initial focused-gate failure instead of closing from stale evidence.
- Fixed the production workflow period resolver so it consults modelo registry deadline-window spelling and preserves both Modelo 130 `YYYYQn` and Modelo 303 `YYYY-nT` quarterly forms.
- Updated file-flow coverage to use the production resolver rather than a duplicated test-local period mapper.
- Kept all verification non-private and read-only; no AEAT write path was invoked.

## Outcome

Passing gates:

- `pytest -q src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/core/test_external_constants.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_actions.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_export.py src/aeat/domain/test_period.py src/aeat/domain/calculations/registry/test_modelo_714_registry.py src/aeat/application/calculations/test_modelo_714_patrimonio_baseline_fidelity.py src/aeat/entrypoints/cli/test_modelo_714_stub_refusal.py` -> 243 passed.
- `ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_actions.py src/aeat/application/modelo/test_file_flow.py src/aeat/domain/calculations/registry/test_modelo_714_registry.py src/aeat/application/calculations/test_modelo_714_patrimonio_baseline_fidelity.py src/aeat/entrypoints/cli/test_modelo_714_stub_refusal.py` -> passed.
- Post-review `ruff check src/aeat/application/modelo/_actions.py` -> passed.

## Notes

The first focused gate failed with six Modelo file-flow failures. That was a real regression: the 303 period fix had made the shared resolver emit `YYYY-nT` for Modelo 130, while the deadline registry declares Modelo 130 quarterly windows as `YYYYQn`. The fix is registry-backed rather than model-specific hardcoding.
