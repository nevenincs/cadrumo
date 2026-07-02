---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S397'
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
     The S397 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
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
     The Retire verify_link_consistency from application.invoices.__all__ and repoint every consumer onto its sole canonical source aeat.domain.invoices and ## Scope

- `src/aeat/application/invoices/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retire verify_link_consistency from application.invoices.__all__ and repoint every consumer onto its sole canonical source aeat.domain.invoices

## Scope

- `src/aeat/application/invoices/__init__.py`
- `src/aeat/application/invoices/tests/test_queries.py`

## Description

- Landed together with S395/S396 in one commit.
- Removed `verify_link_consistency` from `application.invoices`'s import block and `__all__`; confirmed `application.invoices`'s own `_queries.py` submodule already imports it directly from `domain.invoices`.
- Repointed the one real consumer site, `application/invoices/tests/test_queries.py`, merging `verify_link_consistency` into its existing `domain.invoices` import block.
- Updated the module docstring's "Key exports" list, dropping the redundant `LinkInconsistency` phrasing tie-in to the retired function.

## Outcome

Committed at `ed58c5cc5`. `pytest src/aeat/application/invoices/tests/test_queries.py -q` (4 passed). `pytest --collect-only -q src/aeat` clean immediately before commit. `python dev/import_hygiene_scan.py` confirms `verify_link_consistency` no longer appears in the Family-3 findings.

## Notes

None.
