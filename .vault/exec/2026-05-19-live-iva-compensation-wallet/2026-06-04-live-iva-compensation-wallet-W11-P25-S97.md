---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S97'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# W11.P25.S97 Static Live-Test Opt-In Guard

Scope: `src/aeat/core/config.py`, `src/aeat/core/access_gate/__init__.py`, `src/aeat/application/auth/_operator.py`, `src/aeat/tests/test_marker_integrity.py`, `.vault/audit/2026-05-20-live-iva-compensation-wallet-review-audit.md`.

## Description

- Added central config constants for the pytest-only live-read opt-in environment variable and matching Settings field.
- Updated the access gate to consume the centralized env-var constant.
- Updated auth operator settings scoping to consume the neutral centralized field-name constant instead of hardcoding the setting key.
- Added a marker-integrity static guard that scans production Python modules and refuses `AEAT_LIVE_TESTS_ENABLED` / `aeat_live_tests_enabled` usage outside core config/access-gate authority files and test infrastructure.

## Outcome

`W11.P25.S97` is complete. The guard prevents production CLI/application/adapter modules from reintroducing direct test-env gating for operational live reads.

## Notes

The full inventory and marker taxonomy rows are now closed as `W11.P25.S94` and `W11.P25.S96`. `vaultspec-rag` search lock/timeout degradation remains open separately under `W10.P24.S98`; S97 closes only the static production-token guard.

Validation completed:

- `uv run pytest src/aeat/tests/test_marker_integrity.py::test_live_test_opt_in_token_is_not_used_by_production_live_read_paths -q`
- `uv run pytest src/aeat/tests/test_marker_integrity.py src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/core/access_gate/test_override.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py src/aeat/tests/test_config.py::TestEnvExampleAlignment::test_settings_fields_documented_in_env_example src/aeat/tests/test_config.py::TestEnvExampleAlignment::test_env_example_vars_defined_in_settings -q`
- `uv run ruff check src/aeat/core/access_gate/__init__.py src/aeat/core/access_gate/_errors.py src/aeat/core/config.py src/aeat/application/auth/_operator.py src/aeat/application/live/__init__.py src/aeat/entrypoints/cli/_app_live.py src/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/core/access_gate/test_override.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py src/aeat/tests/test_marker_integrity.py`
