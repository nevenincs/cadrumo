---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S391'
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
     The S391 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
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
     The Retire CalculationRevision from application.modelo.__all__ and repoint every consumer onto its sole canonical source aeat.domain.modelos and ## Scope

- `src/aeat/application/modelo/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retire CalculationRevision from application.modelo.__all__ and repoint every consumer onto its sole canonical source aeat.domain.modelos

## Scope

- `src/aeat/application/modelo/__init__.py`
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/_modelo_work_revision_cli.py`
- `src/aeat/application/calculations/tests/test_modelo_130_carry_forward_continuity.py`

## Description

- Landed together with S392/S393/S394 (one commit covers all four retired `application.modelo` symbols, since they share the same `__init__.py` edit and largely the same consumer files).
- Removed `CalculationRevision` from `application.modelo`'s import block and `__all__`; confirmed `application.modelo`'s own submodules already import it directly from `domain.modelos`.
- Repointed the two real consumer sites that imported it from `application.modelo`: `entrypoints/cli/_modelo.py` and `entrypoints/cli/_modelo_work_revision_cli.py` now import `CalculationRevision` from `domain.modelos`.
- Updated the module docstring's `CalculationRevision` cross-references to the fully-qualified `domain.modelos.CalculationRevision` anchor.

## Outcome

Committed at `b2d425a63`. `pytest --collect-only -q src/aeat` clean immediately before commit (12153 tests collected). `python dev/import_hygiene_scan.py` confirms `CalculationRevision` no longer appears in the Family-3 multi-sourced-symbol findings.

## Notes

None.
