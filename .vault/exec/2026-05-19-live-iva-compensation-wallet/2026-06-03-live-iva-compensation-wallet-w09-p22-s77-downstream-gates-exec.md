---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S77'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-w06-p15-s56-wallet-live-success-exec]]'
---

# `live-iva-compensation-wallet` `W09.P22.S77` downstream gates

## Scope

Focused downstream verification after the live AEAT wallet/cartera read succeeded.

## Description

- Audited the Modelo 303 wallet authority path from persisted decision to calculation binding, verification readiness, and export/file guards.
- Re-ran the focused wallet calculation and parser gates.
- Fixed stale wallet backend test fixtures so they use the current cartera result contract: aggregate pending total plus `Ejercicio`, `Período`, and `Cuota Disponible` detail rows.
- Kept all amounts synthetic and avoided live taxpayer identifiers or live wallet amounts in tests and this record.

## Outcome

Passing gates:

- `uv run pytest -q src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py`
- `uv run pytest -q src/aeat/application/modelo/test_actions.py -k iva_wallet`
- `uv run pytest -q src/aeat/application/live/test_iva_wallet_capture_backend.py`
- `uv run ruff check src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/application/live/__init__.py`
- `uv run pytest -q src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`
- `.venv\Scripts\python.exe -m pytest -q src/aeat/application/modelo/test_export.py`

Failure recorded:

- `uv run pytest -q src/aeat/application/modelo/test_export.py` failed before pytest because another process held `.venv\Scripts\aeat.exe`, causing uv's editable-package rebuild to fail with an OS file-lock error. The same test file passed through the existing venv Python without rebuilding.

## Notes

The current downstream evidence supports the wallet decision path for Modelo 303 calculation, readiness blocking for blocked decisions, and export/file refusal for blocked decisions. Remaining S77 work stays open for broader Modelo 390, Modelo 130 relation, and final readiness coverage.
