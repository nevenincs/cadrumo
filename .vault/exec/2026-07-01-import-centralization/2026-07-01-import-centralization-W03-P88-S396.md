---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S396'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Retire suggest_reconciliations from application.invoices.__all__ and repoint every consumer onto its sole canonical source aeat.domain.invoices

## Scope

- `src/aeat/application/invoices/__init__.py`

## Description

- Landed together with S395/S397 in one commit.
- Removed `suggest_reconciliations` from `application.invoices`'s import block and `__all__`; confirmed `application.invoices`'s own `_reconciliation.py` submodule already imports it directly from `domain.invoices`.
- No real cross-package consumer imported `suggest_reconciliations` from `application.invoices`.
- Updated the module docstring's "Key exports" list accordingly.

## Outcome

Committed at `ed58c5cc5`. `pytest --collect-only -q src/aeat` clean immediately before commit. `python dev/import_hygiene_scan.py` confirms `suggest_reconciliations` no longer appears in the Family-3 findings.

## Notes

None.
