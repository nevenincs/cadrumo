---
step_id: S97
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W11.P28.S97 step record

## Step

Implement Clause 10 asserting no pydantic field at a persisted or wire boundary ending in `_kind`, `_status`, or `_state` uses bare `str` with only a length/pattern constraint when a typed alias exists. Wave W11 close gate: verify all 10 clauses pass.

## Status

BLOCKED

## Implementation

Added to `src/aeat/diagnostics/_identity_placement.py`:
- `_is_string_alias_value()` — guards alias discovery to `Literal[...]` and
  `Annotated[str, ...]` only (excludes enum classes sharing `Kind`/`Status`/`State` suffix).
- `build_kind_status_state_alias_inventory()` — discovers 14 string-backed typed aliases.
- `find_bare_str_kind_status_state_fields()` — flags bare-`str` pydantic fields at
  persisted/wire boundaries when a matching string alias exists.

Added to test file:
- `test_kind_status_state_alias_inventory_discovers_known_aliases()` — synthetic proof
  that the inventory discovers `Literal` aliases and ignores enum classes.
- `test_bare_str_kind_status_state_detector_flags_synthetic_violation()` — anti-tautology proof.

## Blocked reason

2 violations in the current tree:

- `src/aeat/application/ledger/_models.py:339` — `LedgerTransactionReviewPayload.review_status: str`
  when `ReviewStatus = Literal['pending', 'approved', 'rejected']` exists.
- `src/aeat/application/ledger/_models.py:363` — `LedgerTransactionResultPayload.review_status: str`
  same alias exists.

Owning wave: W12 (bare-str enrollment / PROMOTE-001, Rule 5).

## W11 close gate

The W11 close gate (all 10 clauses passing sequentially) cannot be declared green while
clauses 5, 6, 7, 8, and 10 have unresolved violations. Only Clause 9 (S96) passes cleanly.

The 17 tests currently in the test file all pass (proof tests for blocked clauses pass;
only the zero-violation assertions for blocked clauses are deferred).

## Commit

`8a08cac3f` — diagnostics(W11.P28): extend enforcement test to 10 clauses per Rule 11

## Files touched

- `src/aeat/diagnostics/_identity_placement.py`
- `src/aeat/diagnostics/test_identity_primitive_placement.py`
