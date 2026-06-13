---
tags: ["#exec", "#live-iva-compensation-wallet"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S03"
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# `live-iva-compensation-wallet` `W03.P03.S03`

Added a multiyear IVA compensation test tying source-period lots to wallet divergence and local filed-history fallback.

- Modified: `src/aeat/application/calculations/test_iva_compensation_history.py`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The new test covers a generated compensation balance in one fiscal year, partial application in a later year, the expiry-boundary review state, and the remaining local balance feeding wallet reconciliation. It verifies that a higher AEAT wallet amount blocks automatic output and that a missing wallet can fall back to the local filed-history recurrence amount.

No live AEAT calls, browser sessions, wallet pulls, form submissions, signing, payment, amendment, or remote mutation paths were run for this step.

The rolling audit records the original coverage gap as `WALLET-044`.

The exact L3 plan row was closed by direct checkbox edit because the current vaultspec step command accepts only duplicate leaf ids such as `S03`.

## Tests

- `uv run pytest src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/calculations/test_observations_repository_roundtrip.py -q` completed with 20 passed.
- `uv run ruff check src/aeat/application/calculations/test_iva_compensation_history.py` passed.
- `git diff --check -- src/aeat/application/calculations/_iva_compensation_history.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_compensation_history.py` passed.
