---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S06'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-ports-inversion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-07-02-arch-remediation-ports-inversion-plan placeholders are machine-filled by
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
     The Relocate the invoices repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries and ## Scope

- `src/aeat/domain/invoices/_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Relocate the invoices repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/invoices/_repository.py`

## Description

- Relocate the concrete `InvoiceCatalogueRepository` plus its two class-private bucket-resolution helpers from `domain/invoices/_repository.py` to the persistence adapter `adapters/persistence/profile/invoices.py`, behind the pre-existing `InvoiceCatalogueRepositoryProtocol`.
- Delete `domain/invoices/_repository.py` whole (no pure functions remained); redeclare the namespace/version constants in the adapter as the persisted-envelope contract.
- Sweep every consumer import to the adapter home with an AST-locate plus clean-unparse rewriter; drop `InvoiceCatalogueRepository` from the domain facade `__all__` while keeping the read-side protocol on the facade.
- Move the two dedicated repository tests (`test_invoices_repository.py`, `test_invoices_secure_storage_roundtrip.py`) to the adapter tests folder; switch their marker from `hex_domain` to `hex_persistence_adapter`.
- Update `.importlinter`, `test_lazy_import_policy.py`, `test_importlinter_ledger.py`, and the apidocs stubs to move the pinned edges and deferral entries from the domain module to the adapter, and drop the `InvoiceCatalogueRepository` core-struct docstring anchor.

## Outcome

- Committed in one atomic explicit-pathspec commit `d1ca224705`, 78 files.
- `pytest --collect-only -q src/aeat` clean; layered import-linter contract KEPT (45 new application/domain adapter-consumer pins); `test_importlinter_ledger` and `test_lazy_import_policy` green (application-to-adapters ratchet 509->557, ADAPTER_INTERNAL_DEFERRAL 148->156, allowlist edge ceiling 479->480); `apidocs scaffold --check` reports no drift; `test_docstring_core_struct_links` green.
- The moved invoice repository roundtrip plus anti-tautology proof and the invoice consumer suites pass against real encrypted SQLite (143 passed in the invoices scope).

## Notes

- The lazy-import gate also declares the pre-existing committed `registry._validate_cross_domain_snapshot -> _ledger_bindings` deferral that landed undeclared upstream, absorbed here to restore the gate to green.
- Peer renta registry work in progress (uncommitted M100 descendientes bindings and schema) is untouched and excluded from this commit; its nine `test_source_resolver` registry-validation failures are working-tree-only and are absent from this commit's tree.
