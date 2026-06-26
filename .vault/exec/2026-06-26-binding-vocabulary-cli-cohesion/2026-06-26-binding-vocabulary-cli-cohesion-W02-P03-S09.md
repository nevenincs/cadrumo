---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S09'
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
     The S09 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Rename the BusinessOperationInvoiceSourceKind TYPE to BusinessOperationInvoiceDirection (invoice-direction axis) KEEPING the payable_invoice / collectible_invoice member STRING values load-bearing per aeat-spanish-stem-naming, as one atomic relocation:BusinessOperationInvoiceSourceKind commit, sweeping all 31 occurrences across the ledger invoice CLI, the invoices _source_resolver, _business_operation_invoice.py, the ledger __init__ re-export, and the two test modules and ## Scope

- `regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/application/ledger/_business_operation_invoice.py`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py`
- `src/aeat/application/invoices/_source_resolver.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename the BusinessOperationInvoiceSourceKind TYPE to BusinessOperationInvoiceDirection (invoice-direction axis) KEEPING the payable_invoice / collectible_invoice member STRING values load-bearing per aeat-spanish-stem-naming, as one atomic relocation:BusinessOperationInvoiceSourceKind commit, sweeping all 31 occurrences across the ledger invoice CLI, the invoices _source_resolver, _business_operation_invoice.py, the ledger __init__ re-export, and the two test modules

## Scope

- `regen docs-scaffold + locale + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/application/ledger/_business_operation_invoice.py`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py`
- `src/aeat/application/invoices/_source_resolver.py`

## Description

- Rename the invoice-direction enum TYPE from the `SourceKind` homonym to `BusinessOperationInvoiceDirection` (the payable-vs-collectible direction axis).
- Preserve the member string values `payable_invoice` and `collectible_invoice` (the load-bearing internal source-kind taxonomy per the Spanish-stem-naming rule); only the type name moves.
- Sweep all 31 occurrences across the ledger invoice CLI, the invoices source-resolver, `_business_operation_invoice` (def, field/param annotations, constructor assignments, `__all__`), the ledger `__init__` re-export, and the two test modules; leave the `invoice_direction_to_source_kind` function name and the `source_kind` record field name untouched.

## Outcome

Landed as one atomic commit `relocation:BusinessOperationInvoiceSourceKind` (`c39039700`). The axis is NOT folded into `BindingSourceKind`. collect-only clean, ruff clean (three import/`__all__` repositionings to the alphabetical slot, each verified as the single own rename move), the 47 ledger-invoice and source-resolver tests green, and the member strings verified unchanged in the staged diff.

## Notes

All six scoped files were clean of peer WIP, so a direct explicit-path stage and verified-index commit were sufficient. The enum docstring was clarified to state the member strings are the load-bearing source-kind taxonomy and only the type name is the direction axis.
