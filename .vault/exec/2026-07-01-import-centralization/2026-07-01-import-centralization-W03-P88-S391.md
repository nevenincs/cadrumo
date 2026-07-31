---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:0b66a9cb5ab6ca980cbc2fa983fb26066a1e2bd737ccb1751d9972c0b299b338'
step_id: 'S391'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

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
