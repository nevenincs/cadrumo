---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S33'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# W02.P06.S33 Cross-Revision Advisory Summary Extraction

Scope: extract advisory cross-revision drift summary helpers.

## Description

- Added `_validate_cross_revision_advisory.py` for the advisory drift summary dataclass and summarizer.
- Kept `_validate_cross_revision.py` re-exporting the advisory API so existing imports remain stable.
- Verified the cross-revision drift test module and public import identity.

## Outcome

Advisory non-overlapping drift inventory logic now lives outside the strict cross-revision validator module, reducing the next extraction surface without changing behavior.

## Notes

No public registry imports changed.
