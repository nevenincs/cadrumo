---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S394'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

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
