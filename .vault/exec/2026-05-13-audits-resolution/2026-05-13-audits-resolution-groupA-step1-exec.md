---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-eliminate-shims-audit]]"
---

# audits-resolution group-a step-1

## scope

Plan row A1: add `strict=True` to four application-layer pydantic
records that cross the persistence boundary.

Records updated:

- `AuthState` in `src/aeat/application/auth/_models.py`
- `WorkflowEvent`, `DeclarationPointer`, `WorkflowState` in
  `src/aeat/application/workflow/_models.py`
- `LedgerSplit`, `LedgerReviewRecord`, `InvoiceReviewRecord` in
  `src/aeat/application/review/_models.py`
- `ProfileRecord` in `src/aeat/application/profile/_models.py`

Each record's `model_config` now carries the canonical
`strict=True, frozen=True, extra="forbid"` triple.

## verification

`pytest src/aeat/application/auth/ src/aeat/application/workflow/
src/aeat/application/review/ src/aeat/application/profile/ -q` green
with 293 passed.

`grep -n 'ConfigDict' src/aeat/application/{auth,workflow,review,profile}/_models.py`
confirms every cited record carries `strict=True`.
