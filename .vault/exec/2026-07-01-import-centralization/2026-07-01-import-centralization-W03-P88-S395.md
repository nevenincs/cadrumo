---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:3255cec3b1a59ff12096175fc331db3eb9050414f50b9ad0d5d7132c92212591'
step_id: 'S395'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

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
