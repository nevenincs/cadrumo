---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S05'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Promote `DEFAULT_MAX_WALLET_AGE_DAYS`, `IvaCompensationAuthoritySource`, `IvaCompensationReconciliationDecision`, `IvaCompensationWalletObservationProtocol`, `local_recurrence_authority_source`, `reconcile_iva_compensation_wallet`, `validate_wallet_matches_snapshot` to `aeat.domain.iva_compensation.__all__` with eager re-exports so the 13 existing cross-package consumer site(s) can import from the facade

## Scope

- `src/aeat/domain/iva_compensation/__init__.py`
## Description

- Reconcile $display as an individual exec record for a W01 facade-promotion row already checked in the plan.
- Preserve the row intent: Promote `DEFAULT_MAX_WALLET_AGE_DAYS`, `IvaCompensationAuthoritySource`, `IvaCompensationReconciliationDecision`, `IvaCompensationWalletObservationProtocol`, `local_recurrence_authority_source`, `reconcile_iva_compensation_wallet`, `validate_wallet_matches_snapshot` to `aeat.domain.iva_compensation.__all__` with eager re-exports so the 13 existing cross-package consumer site(s) can import from the facade.
- Tie this row to the `application.live` / `domain.iva_compensation` / `application.calculations` W01 facade-promotion batch, landed in `2590a235f6` and recorded by the existing `W01.P05.S04` exec record.
- Record no new implementation work; this document splits already-landed umbrella evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching umbrella evidence for $anchor recorded live import probes for the three facades, `ruff check`, `pytest --collect-only -q src/aeat`, and a 651-test targeted slice green. The W01 scaffold pass removed $(W01.P06.S05.Split('.')[-1]) from xec_missing_ids at plan status time.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W01 landing, so this record intentionally cites the historical landed evidence and does not claim a fresh source edit.
