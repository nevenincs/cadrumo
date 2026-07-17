---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# Verify W02.P03 no-shift: run pytest --collect-only -q clean, the reconcile / ledger-invoice / iva-compensation test modules green, and assert the C2 member string values payable_invoice / collectible_invoice are unchanged

## Scope

- `confirm none of the three axes were folded into BindingSourceKind`
- `src/aeat/application/modelo/tests`
- `src/aeat/application/ledger/tests`
- `src/aeat/domain/iva_compensation`

## Description

- Confirm none of the three renamed axes (`ModeloReconciliationEvidenceKind`, `BusinessOperationInvoiceDirection`, `IvaCompensationAuthorityKind`) were folded into `BindingSourceKind` (zero core-module members).
- Assert the C2 member strings `payable_invoice` and `collectible_invoice` are unchanged.
- Run the reconcile, ledger-invoice, source-resolver, and iva-compensation test modules plus the bindings-framework gate suite.

## Outcome

W02.P03 no-shift proven. The three axes stay distinct and unfolded. The C2 member strings are present and unchanged. collect-only clean (16463 collected; the modest rise above the W01 baseline is peer-driven test additions in the shared worktree, not this work, with no collection errors). The bindings-framework gate suite ran 98 passed; the C1/C2/C3 consumer test modules ran 15 + 47 + 33 passed.

## Notes

None.
