---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F10'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` `W04.F10`

Made Cl@ve timeout diagnostics carry exact operator phone-state report commands.

- Modified: `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`
- Modified: `src/aeat/application/auth/_diagnostics.py`
- Modified: `src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`

## Description

The unresolved WALLET-058 live timeout cannot be fixed safely without operator phone-state testimony. This step improves the offline diagnostic contract so the next timeout artefact contains exact report commands for every allowed phone state: prompted and accepted, prompted but not accepted, no app prompt, and operator did not check.

The allowed phone-state tuple now lives in the Cl@ve auth module and is reused by application diagnostics. The timeout error context stores both the allowed values and the exact commands, and the suggestion renders those commands directly. Persisted diagnostic detail also exposes the same commands through `aeat config auth diagnostics show DIAGNOSTIC_ID`.

No live AEAT operation was performed in this step.

## Tests

- `uv run pytest src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::TestClaveWaitState src/aeat/application/auth/test_diagnostics.py -q --disable-warnings` completed with 5 passed.
- `uv run pytest src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/application/auth/test_diagnostics.py src/aeat/core/test_external_constants.py -q --disable-warnings` completed with 57 passed.
- `uv run ruff check src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_diagnostics.py src/aeat/entrypoints/cli/_config/__init__.py` passed.
