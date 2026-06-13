---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S95'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# W11.P25.S95 Live-Test Gate Separation

Scope: `src/aeat/core/access_gate/__init__.py`, `src/aeat/core/access_gate/_errors.py`, `src/aeat/core/config.py`, `src/aeat/application/auth/_operator.py`, `src/aeat/application/live/__init__.py`, `src/aeat/entrypoints/cli/_app_live.py`, `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`, `src/aeat/adapters/outbound/aeat/auth/test_gate.py`, `src/aeat/core/access_gate/test_override.py`, `src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py`, `.vault/audit/2026-05-20-live-iva-compensation-wallet-review-audit.md`, `.vault/audit/2026-06-03-live-iva-compensation-wallet-code-review-audit.md`.

## Description

- Reworked `AeatAccessGate.require_live_read` so `AEAT_LIVE_TESTS_ENABLED` is required only while pytest is executing a live read.
- Kept operator live reads flowing to the existing authentication, profile storage, read-only remote-state, and no-submit guards instead of refusing on the pytest opt-in value.
- Routed `login_operator_auth` through the central access gate and translated the typed pytest-only refusal into the existing localized auth-login refusal.
- Updated stale production comments that described `AEAT_LIVE_TESTS_ENABLED` as an operator-shell live-read precondition.
- Added focused tests proving non-pytest operator context is admitted, pytest context is still refused without literal `1`, and auth login reaches provider preconditions outside pytest.

## Outcome

`W11.P25.S95` is complete. `W11.P25.S94`, `W11.P25.S96`, and `W11.P25.S97` remain open for full inventory, pytest marker taxonomy hardening, and static guard enforcement.

## Notes

`vaultspec-rag search` could not be used for the inventory portion because the local store remained locked or timed out. That failure is tracked under `W10.P24.S98` and was not treated as evidence that the broader inventory row is complete.

Validation completed:

- `uv run ruff check src/aeat/core/access_gate/__init__.py src/aeat/core/access_gate/_errors.py src/aeat/core/config.py src/aeat/application/auth/_operator.py src/aeat/application/live/__init__.py src/aeat/entrypoints/cli/_app_live.py src/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/core/access_gate/test_override.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py`
- `uv run pytest src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/core/access_gate/test_override.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py -q`
- `uv run pytest src/aeat/entrypoints/cli/test_registry_cli.py::test_list_filed_data_cli_requires_live_gate_before_remote_read src/aeat/entrypoints/cli/test_registry_cli.py::test_capture_filed_data_cli_requires_live_gate_before_local_writes src/aeat/entrypoints/cli/test_registry_cli.py::test_capture_iva_history_cli_requires_live_gate_before_local_writes src/aeat/entrypoints/cli/test_registry_cli.py::test_capture_source_filed_data_requires_live_gate_before_local_writes -q`
- `uv run pytest src/aeat/application/live/test_iva_live_failure_taxonomy.py src/aeat/application/live/test_iva_wallet_live.py -q`
