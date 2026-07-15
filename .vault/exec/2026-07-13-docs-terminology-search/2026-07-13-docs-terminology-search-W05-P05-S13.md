---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S13'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---




# Gate the weight table: its ordering matches the ADR D8 ladder verbatim and every display class carries exactly one weight, failing on any unmapped class

## Scope

- `dev/docs/terminology/tests/test_unified_record.py`

## Description

- Add a ladder-verbatim gate that pins the declared weight table to the ADR D8 ordering: `doc` greater than `modelo` greater than `casilla` greater than `cli` greater than `technical`, strictly descending so no two adjacent classes share a rank band and the ordering is unambiguous.
- Assert every display class carries exactly one weight and the weights lie in the unit interval, so an unmapped class (or a table key that is not an enum member) fails the gate.
- Assert the two D8 amendments explicitly: casilla now outranks cli within the navigation tier, and technical is the strict minimum (below user-documentation `doc`).
- Derive the expected ordering strictly from the ADR ladder prose, never copied from the table under test.

## Outcome

- A future reorder of the declared per-class weight table fails the gate loudly, and a class added without a weight fails it. The gate is green alongside the coverage gate and the existing unified-record suite (nineteen tests passed).

## Notes

- The gate landed as a dedicated new test module rather than inside `test_unified_record.py` (the same coordinator-directed split as the coverage gate), keeping the ranking-ladder assertions isolated and off the shared unified-record test file during concurrent casilla work.
