---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S54'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W05.P15.S54 - remote-state planned-operation conformance gate

Scope: Wave `W05`; Phase `W05.P15`; Step `S54`.

## Description

- Added `assert_remote_operations_allowed` as the shared multi-operation guard preflight.
- Routed live-parity oracle preflight through the shared remote-state guard helper.
- Added a committed-registry test that resolves bound production oracles and preflights their real planned operations against the registry-declared guard policies.
- Extended the write-token guard to reject `confirmar` and `confirmacion` browser actions.

## Outcome

The S54 gate is closed. Bound committed registry oracle plans for M349 GROI and IXVI/NIF-IVA now fail CI if their planned `RemoteOperation` sequence drifts outside the declared read-only guard policy.

## Notes

M100 Renta WEB Open is registered as a production oracle and has a guard policy fixture, but the committed M100 live cross-reference does not yet declare `oracle_id = "modelo-100-renta-web-open"`. The S54 gate is ready for that binding and will cover it once the legal-data binding is added in a dedicated registry slice.

Verification:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_remote_state_guard.py src/aeat/domain/calculations/registry/_live_parity.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_remote_state_guard.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_remote_state_guard.py src/aeat/domain/calculations/registry/test_live_parity.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py src/aeat/domain/calculations/registry/test_groi_oracle.py src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py`
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py src/aeat/domain/calculations/registry/test_groi_oracle.py src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py`
