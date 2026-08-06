---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:572242c1fed473d4480f01cbe4f4cdbde5d9e493c62d55da364a2fbbb7344e94'
step_id: 'S397'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

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
