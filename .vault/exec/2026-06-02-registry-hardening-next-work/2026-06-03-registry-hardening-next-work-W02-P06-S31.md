---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S31'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# W02.P06.S31 Validator Decomposition Boundary Audit

Scope: audit validator responsibilities and choose safe extraction boundaries.

## Description

- Promoted the registry hardening next-work plan to L3 and added W02 for validation module decomposition.
- Measured the existing validator modules and confirmed `_validate.py` is now an orchestration module.
- Identified `_validate_cross_revision.py` as the first real extraction target.
- Verified the touched validator modules still compile.

## Outcome

S31 found that no immediate extraction should start in `_validate.py`; the next implementation step should split cross-revision validator policies while preserving public exports.

## Notes

No production code was changed in this step. Feature-scoped dangling-link check is blocked by pre-existing May schema-hardening audit links, unrelated to the S31 artifacts.
