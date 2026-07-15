---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S24'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# pin the intentional split with a regression test asserting K L M are not in _CIF_KIND_LETTERS while validate_spanish_tax_id still accepts a K-led valid CIF

## Scope

- `prevents future consolidation from silently collapsing the two sets`
- `src/aeat/core/identity/test_documents.py`

## Description

- Reconciled the CIF contract regression test to the Wave-1 commit review.
- Confirmed `c55954263` supplied the reviewed change and pinning test.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-27 review accepted the regression coverage. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S22 and S23; each row receives its own record.
