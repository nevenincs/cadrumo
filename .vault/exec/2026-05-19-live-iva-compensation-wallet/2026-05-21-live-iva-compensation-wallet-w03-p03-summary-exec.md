---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` `W03.P03` summary

Completed the cross-year and multiyear carry-forward tracking phase for `W03.P03.S01` through `W03.P03.S03`.

- Modified: `src/aeat/application/calculations/_iva_compensation_history.py`
- Modified: `src/aeat/application/calculations/__init__.py`
- Created: `src/aeat/application/calculations/test_iva_compensation_history.py`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`
- Created: `.vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p03-s01.md`
- Created: `.vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p03-s02.md`
- Created: `.vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p03-s03.md`

## Description

The phase added source-period IVA compensation carry-forward lots over filed Modelo 303 history. Generated balances are tracked by source filing year and period, later applications consume earlier lots FIFO, remaining balances are preserved, and each lot carries age and expiry-review state.

The phase also added an explicit four-year policy gate for expired remaining lots and a multiyear scenario tying source-period remaining balances to AEAT wallet divergence and local filed-history fallback.

No live AEAT calls, browser sessions, wallet pulls, form submissions, signing, payment, amendment, or remote mutation paths were run during this phase.

The rolling audit captures the phase issues and mitigations as `WALLET-042`, `WALLET-043`, and `WALLET-044`.

## Tests

- `uv run pytest src/aeat/application/calculations/test_iva_compensation_history.py -q` completed with 6 passed.
- `uv run pytest src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/calculations/test_observations_repository_roundtrip.py -q` completed with 20 passed.
- `uv run ruff check src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.
- `git diff --check -- src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.
