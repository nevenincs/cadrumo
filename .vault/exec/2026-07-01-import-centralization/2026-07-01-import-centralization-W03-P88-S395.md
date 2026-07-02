---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S395'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace import-centralization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S395 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
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
     The Retire link_transaction from application.invoices.__all__ and repoint every consumer onto its sole canonical source aeat.domain.invoices and ## Scope

- `src/aeat/application/invoices/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retire link_transaction from application.invoices.__all__ and repoint every consumer onto its sole canonical source aeat.domain.invoices

## Scope

- `src/aeat/application/invoices/__init__.py`

## Description

- Landed together with S396/S397 in one commit (all three retired `application.invoices` symbols share one `__init__.py` edit).
- Removed `link_transaction` from `application.invoices`'s import block and `__all__`; confirmed `application.invoices`'s own submodules (`_linking.py`, `_reconciliation.py`) already import it directly from `domain.invoices`.
- No real cross-package consumer imported `link_transaction` from `application.invoices` (verified via a precise AST walk over every `ImportFrom` resolving to `aeat.application.invoices`).
- Updated the module docstring's "Key exports" list to drop the local mention and note the symbol's sole canonical source.

## Outcome

Committed at `ed58c5cc5`. `pytest --collect-only -q src/aeat` clean immediately before commit. `python dev/import_hygiene_scan.py` confirms `link_transaction` no longer appears in the Family-3 findings.

## Notes

None.
