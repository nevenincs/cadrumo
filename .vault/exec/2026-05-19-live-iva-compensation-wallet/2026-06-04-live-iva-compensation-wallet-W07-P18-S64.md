---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S64'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# live-iva-compensation-wallet W07.P18.S64

Scope: persisted divergence decisions and separate authority-source retention.

## Description

- Audit existing reconciliation and secure-storage coverage for source-merging gaps.
- Confirm existing reconciliation tests cover match, wallet-only, wallet-higher, wallet-lower, missing wallet, filed-history-only, stale wallet, and taxpayer override outcomes.
- Add secure-storage roundtrip coverage for a non-private override decision carrying AEAT wallet, local recurrence, filed-history observation, and taxpayer override authority sources.
- Assert selected, wallet, local, override, and per-source amounts remain distinct after latest/history/list reloads.
- Assert encrypted SQL bytes do not contain the synthetic taxpayer id or override evidence locator.

## Outcome

Persisted IVA compensation divergence decisions now have regression coverage proving the storage backend preserves separate authority sources and amounts. The proof uses the production `IvaWalletDecisionRepository` and does not mirror reconciliation arithmetic in the test.

Verification passed:

- `python -m pytest -q src/aeat/application/calculations/test_observations_repository_roundtrip.py::test_iva_wallet_reconciliation_decision_roundtrip_preserves_separate_authority_sources src/aeat/application/calculations/test_observations_repository_roundtrip.py::test_iva_wallet_reconciliation_decisions_keep_immutable_history src/aeat/application/calculations/test_iva_wallet_reconciliation.py`
- `python -m ruff check src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py`

## Notes

No live AEAT request was made. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
