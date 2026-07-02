---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S393'
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
     The S393 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
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
     The Retire ExternalEvidenceKind from application.modelo.__all__ and repoint every consumer onto its sole canonical source aeat.domain.modelos and ## Scope

- `src/aeat/application/modelo/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retire ExternalEvidenceKind from application.modelo.__all__ and repoint every consumer onto its sole canonical source aeat.domain.modelos

## Scope

- `src/aeat/application/modelo/__init__.py`
- `src/aeat/entrypoints/cli/_modelo_records_cli.py`
- `src/aeat/application/calculations/tests/test_modelo_130_carry_forward_continuity.py`

## Description

- Landed together with S391/S392/S394 in one commit.
- Removed `ExternalEvidenceKind` from `application.modelo`'s import block and `__all__`; `application.modelo`'s own submodules already import it directly from `domain.modelos`.
- Repointed the two real consumer sites: `entrypoints/cli/_modelo_records_cli.py` (merged into its existing `domain.modelos` import block) and `application/calculations/tests/test_modelo_130_carry_forward_continuity.py`.
- Updated the module docstring's `ExternalEvidenceKind` cross-reference (it was already fully-qualified as `domain.modelos.ExternalEvidenceKind` in this docstring, so no further change needed there beyond the added ruling-5 note).

## Outcome

Committed at `b2d425a63`. `pytest --collect-only -q src/aeat` clean immediately before commit. `python dev/import_hygiene_scan.py` confirms `ExternalEvidenceKind` no longer appears in the Family-3 findings.

## Notes

None.
