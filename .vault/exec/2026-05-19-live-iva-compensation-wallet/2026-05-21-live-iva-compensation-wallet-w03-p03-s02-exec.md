---
tags: ["#exec", "#live-iva-compensation-wallet"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S02"
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# `live-iva-compensation-wallet` `W03.P03.S02`

Added a four-year IVA compensation carry-forward policy gate over source-dated lots.

- Modified: `src/aeat/application/calculations/_iva_compensation_history.py`
- Modified: `src/aeat/application/calculations/__init__.py`
- Modified: `src/aeat/application/calculations/test_iva_compensation_history.py`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

Added `enforce_iva_compensation_four_year_window`, which refuses remaining carry-forward lots whose source-dated review state is expired. The gate operates on source filing year and source period, so it cannot be satisfied by a same-year aggregate recurrence that hides old balances.

Fully applied expired lots remain allowed because no remaining amount can be carried into a future calculation.

No live AEAT calls, browser sessions, wallet pulls, form submissions, signing, payment, amendment, or remote mutation paths were run for this step.

The rolling audit records the original policy gap as `WALLET-043`.

The exact L3 plan row was closed by direct checkbox edit because the current vaultspec step command accepts only duplicate leaf ids such as `S02`.

## Tests

- `uv run pytest src/aeat/application/calculations/test_iva_compensation_history.py -q` completed with 6 passed.
- `uv run pytest src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/calculations/test_observations_repository_roundtrip.py -q` completed with 19 passed.
- `uv run ruff check src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.
- `git diff --check -- src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.
