---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S392'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Retire CalculationRevisionAmendmentKind from application.modelo.__all__ and repoint every consumer onto its sole canonical source aeat.domain.modelos

## Scope

- `src/aeat/application/modelo/__init__.py`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Landed together with S391/S393/S394 in one commit.
- Removed `CalculationRevisionAmendmentKind` from `application.modelo`'s import block and `__all__`; `application.modelo`'s own submodules already import it directly from `domain.modelos`.
- Repointed the one real consumer site (`entrypoints/cli/_modelo.py`) onto `domain.modelos`.
- Updated the module docstring's `CalculationRevisionAmendmentKind` cross-reference to the fully-qualified `domain.modelos.CalculationRevisionAmendmentKind` anchor.

## Outcome

Committed at `b2d425a63`. `pytest --collect-only -q src/aeat` clean immediately before commit. `python dev/import_hygiene_scan.py` confirms `CalculationRevisionAmendmentKind` no longer appears in the Family-3 findings.

## Notes

None.
