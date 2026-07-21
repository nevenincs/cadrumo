---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S04'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Assert readOnlyHint and destructiveHint annotation coverage on every descriptor and close any gap

## Scope

- `src/aeat/entrypoints/mcp/_annotations.py`

## Description

- Add `annotations_are_covered` defining when a descriptor's read-only / destructive hints are present and mutually consistent, and `annotation_coverage_gaps` sweeping a descriptor set for violations, to `_annotations.py`.
- Enforce the same guard at construction inside `annotations_for_command`, so the server build and the tests inherit full coverage from one shared place.
- Add tests asserting full coverage over every live descriptor plus unit checks on the coverage predicate.

## Outcome

Every exposed descriptor carries consistent read-only and destructive hints: the sweep over all live descriptors returns no gaps, and a contradictory or read-only-non-idempotent annotation is correctly reported as a gap. The coverage function is shared by the descriptor build (through the construction guard) and the tests, so a future descriptor that drifted from the contract would fail loudly rather than silently ship an ambiguous confirmation hint. Ruff check/format clean, pyright clean, and the mcp suite is green at 59 passed.

## Notes

Coverage here is not merely presence (the hints are non-optional booleans and always present) but internal consistency against the mutability contract: a tool is never both read-only and destructive, and a read-only tool is idempotent. The existing `annotations_for_command` mapping already satisfies these invariants, so the guard is defensive and can only fire on a future coding regression - which is exactly the gap the shared function closes.
