---
tags: ["#exec", "#live-iva-compensation-wallet"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S01"
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# `live-iva-compensation-wallet` `W03.P03.S01`

Modelled IVA compensation carry-forward lots across fiscal years with source period, age, applied amount, remaining amount, and expiry-review state.

- Modified: `src/aeat/application/calculations/_iva_compensation_history.py`
- Modified: `src/aeat/application/calculations/__init__.py`
- Created: `src/aeat/application/calculations/test_iva_compensation_history.py`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

Added a carry-forward projection over secure Modelo 303 compensation history. The projection turns generated compensation amounts into source-period lots, applies later compensation usage FIFO against prior lots, preserves remaining balances, reports unallocated applications, and stamps every lot with age and expiry-review state.

This step intentionally models review state without refusing expired or due-for-review amounts. The hard LIVA art. 99 four-year policy gate is the next plan step.

No live AEAT calls, browser sessions, wallet pulls, form submissions, signing, payment, amendment, or remote mutation paths were run for this step.

The rolling audit records the original modelling gap as `WALLET-042`.

The exact L3 plan row was closed by direct checkbox edit because the current vaultspec step command accepts only duplicate leaf ids such as `S01`.

## Tests

- `uv run pytest src/aeat/application/calculations/test_iva_compensation_history.py -q` completed with 4 passed.
- `uv run pytest src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/calculations/test_observations_repository_roundtrip.py -q` completed with 17 passed.
- `uv run ruff check src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.
- `git diff --check -- src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.
