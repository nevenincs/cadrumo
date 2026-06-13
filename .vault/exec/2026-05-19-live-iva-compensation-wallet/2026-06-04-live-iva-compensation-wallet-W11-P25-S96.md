---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S96'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# W11.P25.S96 Live Marker Taxonomy Closeout

Scope: `src/aeat/tests/_marker_hook.py`, `src/aeat/tests/conftest.py`, `src/aeat/tests/test_marker_integrity.py`, `src/aeat/application/conftest.py`, `pyproject.toml`, `.vault/audit/2026-05-20-live-iva-compensation-wallet-review-audit.md`.

## Description

- Verified the shared marker hook enforces exactly one access marker, requires a domain marker, and drops `live_write` collection items with no bypass.
- Verified `src/aeat/tests/conftest.py` skips `live_read` items unless the pytest live-test opt-in is truthy.
- Verified `src/aeat/application/conftest.py` excludes live tests from the autouse isolated-root fixture so live runs use the operator profile state rather than synthetic test roots.
- Kept marker-integrity coverage for marker registry uniqueness, module-level marker placement, function-level access/domain marker refusal, runtime live-test env access scoping, and production live-test opt-in token refusal.
- Removed `AEAT_LIVE_TESTS_ENABLED=0` from ordinary cold-process CLI unit-test helper snippets.

## Outcome

`W11.P25.S96` is complete. The live marker taxonomy remains enforced by collection-time hooks and static tests, while operator CLI live reads are no longer gated by the test opt-in outside pytest.

## Notes

Validation completed:

- `uv run pytest src/aeat/tests/test_marker_integrity.py src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/core/access_gate/test_override.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py src/aeat/tests/test_config.py::TestEnvExampleAlignment::test_settings_fields_documented_in_env_example src/aeat/tests/test_config.py::TestEnvExampleAlignment::test_env_example_vars_defined_in_settings -q`
- `uv run pytest src/aeat/entrypoints/cli/test_cold_start_wizard_registration.py::test_cold_process_work_create_registers_wizard_catalogue -q`
- `uv run pytest src/aeat/entrypoints/cli/test_work_calculate_row_flag.py::TestRevisionViewSurfacesDetailRows::test_m184_member_rows_surface_in_revision_view -q`
- `uv run ruff check src/aeat/core/access_gate/__init__.py src/aeat/core/access_gate/_errors.py src/aeat/core/config.py src/aeat/application/auth/_operator.py src/aeat/application/live/__init__.py src/aeat/entrypoints/cli/_app_live.py src/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/core/access_gate/test_override.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py src/aeat/tests/test_marker_integrity.py`
