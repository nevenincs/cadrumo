---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W04.F22'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-code-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-persona-testimonials-audit]]'
---

# `live-iva-compensation-wallet` `W04.F22`

Corrected the recovery suggestion for corrupt persisted auth sessions.

- Modified: `src/aeat/core/errors/registry/_application.py`

## Description

The config-domain persona pass found that `aeat config auth test --provider clave_movil` correctly failed on a corrupt local persisted session, but the registry-level suggestion pointed to `aeat config auth test --provider certificate`. That was inconsistent with the localized error body and with the operator's selected provider.

The error registry now suggests `aeat config auth clear --sessions`, which is provider-neutral and matches the actual recovery route exposed by `aeat config auth clear --help`.

No live AEAT operation was performed in this step.

## Tests

- `uv run pytest src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/application/auth/test_operator.py src/aeat/application/test_state_projection.py -q --disable-warnings` completed with 42 passed.
- `uv run pytest src/aeat/application/auth/test_operator.py src/aeat/application/test_state_projection.py src/aeat/application/test_diagnostics.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_error_registry_contract.py -q --disable-warnings` completed with 85 passed.
- `uv run ruff check src/aeat/application/state_projection.py src/aeat/application/auth/_operator.py src/aeat/application/auth/test_operator.py src/aeat/core/errors/registry/_application.py src/aeat/application/diagnostics.py src/aeat/application/test_diagnostics.py` passed.
- `uv run aeat config auth test --provider clave_movil` still failed on the known corrupt local session, but now suggested `aeat config auth clear --sessions`.
