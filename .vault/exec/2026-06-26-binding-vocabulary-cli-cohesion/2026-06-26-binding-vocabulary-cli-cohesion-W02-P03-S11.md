---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S11'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Verify W02.P03 no-shift: run pytest --collect-only -q clean, the reconcile / ledger-invoice / iva-compensation test modules green, and assert the C2 member string values payable_invoice / collectible_invoice are unchanged and ## Scope

- `confirm none of the three axes were folded into BindingSourceKind`
- `src/aeat/application/modelo/tests`
- `src/aeat/application/ledger/tests`
- `src/aeat/domain/iva_compensation` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
