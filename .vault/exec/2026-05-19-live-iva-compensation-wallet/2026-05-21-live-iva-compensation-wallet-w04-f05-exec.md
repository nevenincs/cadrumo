---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F05'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# W04.F05 injected wallet-decision repository guards

## Scope

- Follow-up: `W04.F05`
- Goal: make blocked IVA wallet decisions repository-injectable across verify, internal file, and export paths so service callers using explicit secure SQL repositories get the same safety gate as default production storage.

## Changes

- `verify_modelo_revision` uses the caller-provided `IvaWalletDecisionRepository` when appending blocked-wallet verification findings.
- `file_modelo_revision` refuses a verified Modelo 303 revision before filing-state mutation when the injected wallet repository contains a blocked decision.
- `export_modelo_revision` refuses before building or writing a local export artifact when the injected wallet repository contains a blocked decision.
- Added real encrypted SQL-backed tests for verify, internal file, and export where the wallet decision is stored in a separate repository from the default application database, proving the injected repository is the authority source.

## Verification

- `uv run pytest src/aeat/application/modelo/test_export.py -q`
- `uv run pytest src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py -q` completed with 13 passed.
- `uv run ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py`
- `git diff --check -- src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py`
