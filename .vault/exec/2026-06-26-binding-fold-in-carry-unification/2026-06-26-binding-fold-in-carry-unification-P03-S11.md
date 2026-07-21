---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

# vaultspec-high-executor: reconcile the registry previous_filing compensacion formula path to feed or defer to the iva-wallet authority disposition-aware, removing the back-door observation-injection second route (apply-cached on collision, peer-WIP likely)

## Scope

- `src/aeat/application/calculations/_iva_wallet_reconciliation.py`

## Description

- Anchor the Modelo 303 compensación carry on the iva-wallet decision authority by removing the back-door IVA-compensation-history injection from the generic binding-resolution path.
- Stop `resolve_bindings_from_local_store` defaulting the IVA history repository to a real repository; pass the caller's value through so the previous_filing gather stays pure (registry observations only).
- Default the IVA history repository explicitly inside the wallet-feeding `extract_modelo_303_local_iva_compensation_recurrence` so it keeps reconstructing the local recurrence the reconciliation compares against live wallet evidence.

## Outcome

- Landed in the P03 commit `fe86795fa`. The live calculate path's compensación value is already owned exclusively by the iva-wallet decision (ruling D3 exclusion), so the injected value was always discarded there; removing the implicit injection shifts no calculate value. The wallet-engine integration, binding-prefill, and filed-capture suites pass (64 tests).

## Notes

- Scope finding: M303 declares exactly ONE previous_filing binding (the compensación one, already wallet-owned and excluded from the live previous_filing resolution), so the injection had no other live binding to affect. The risk surface of the removal was concentrated entirely in the wallet's local-recurrence reconstruction, which is preserved by the explicit-default relocation.
