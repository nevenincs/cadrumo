---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S394'
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
     The S394 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
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
     The Retire WorkUnit from application.modelo.__all__ and repoint every consumer onto its sole canonical source aeat.domain.modelos and ## Scope

- `src/aeat/application/modelo/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retire WorkUnit from application.modelo.__all__ and repoint every consumer onto its sole canonical source aeat.domain.modelos

## Scope

- `src/aeat/application/modelo/__init__.py`
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/_modelo_reconcile_cli.py`
- `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`
- `src/aeat/entrypoints/cli/_modelo_work_revision_cli.py`
- `src/aeat/application/workflow/_resume.py`

## Description

- Landed together with S391/S392/S393 in one commit.
- Removed `WorkUnit` from `application.modelo`'s import block and `__all__`; `application.modelo`'s own submodules already import it directly from `domain.modelos`.
- Repointed the five real consumer sites: `entrypoints/cli/_modelo.py`, `_modelo_reconcile_cli.py`, `_modelo_work_calculate_cli.py` (a `TYPE_CHECKING`-only import), `_modelo_work_revision_cli.py`, and `application/workflow/_resume.py` (also `TYPE_CHECKING`-only, verified via a working-tree-swap regression check that a pre-existing, unrelated test failure in `test_work_resume.py` reproduces identically against the original HEAD content — confirming the retirement introduces no behavioral change).
- Updated the module docstring's `WorkUnit` cross-reference to the fully-qualified `domain.modelos.WorkUnit` anchor.

## Outcome

Committed at `b2d425a63`. `pytest --collect-only -q src/aeat` clean immediately before commit. `python dev/import_hygiene_scan.py` confirms `WorkUnit` no longer appears in the Family-3 findings.

## Notes

`test_work_resume.py`'s integration suite fails with a `StorageValidationError` ("storage runtime is not ready for profile-bound storage") that is entirely unrelated to this Step — reproduced identically with `application/workflow/_resume.py` reverted to its exact HEAD content, proving the failure is pre-existing/environmental, not caused by this retirement.
