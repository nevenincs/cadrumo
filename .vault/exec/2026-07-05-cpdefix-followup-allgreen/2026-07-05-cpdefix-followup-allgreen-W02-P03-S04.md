---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S04'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cpdefix-followup-allgreen with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-05-cpdefix-followup-allgreen-plan placeholders are machine-filled by
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
     The Prove the current M347 summary route remains invoice-owned and does not falsely promote reserved counterpart sources and ## Scope

- `src/aeat/_data/registry/aeat/modelos/347/revisions/2008-y-siguientes/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove the current M347 summary route remains invoice-owned and does not falsely promote reserved counterpart sources

## Scope

- `src/aeat/_data/registry/aeat/modelos/347/revisions/2008-y-siguientes/`

## Description

- Run RAG code and vault discovery for M347 invoice-owned summary bindings and reserved counterpart-provider promotion.
- Confirm the current M347 summary binding file declares `collectible_invoice`, not `ledger_transaction` or `purchase_invoice_evidence`.
- Confirm the registry test asserts the two M347 summary bindings are invoice-owned and disjoint from reserved provider sources.
- Confirm the counterpart service test keeps the reserved resolver from claiming invoice-owned M347 registry bindings.
- Run the focused M347 registry and counterpart service gate.

## Outcome

M347 source ownership is current and intentionally invoice-owned:

- `0001-counterpart-summary.toml` declares both summary bindings with `source = "collectible_invoice"`.
- `test_modelo_347_registry_bindings.py` asserts the summary bindings are `BindingSourceKind.COLLECTIBLE_INVOICE` and disjoint from `BindingSourceKind.LEDGER_TRANSACTION` / `BindingSourceKind.PURCHASE_INVOICE_EVIDENCE`.
- `test_per_modelo_service.py` asserts the counterpart resolver returns no binding values, provenance, or transaction ids for the invoice-owned M347 summary route.

Verification passed:

`uv run --no-sync pytest -q -n 0 src/aeat/domain/calculations/registry/tests/test_modelo_347_registry_bindings.py src/aeat/application/aggregation/tests/test_per_modelo_service.py -k "counterpart" --tb=short`

Result: 4 passed, 23 deselected.

No code changes were required.

## Notes

The old "M347 has no bindings" blocker is stale. The current route does not fire the counterpart-provider promotion trigger because it does not declare the reserved sources.
