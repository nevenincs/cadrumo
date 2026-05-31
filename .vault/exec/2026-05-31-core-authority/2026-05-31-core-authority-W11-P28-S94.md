---
step_id: S94
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W11.P28.S94 step record

## Step

Implement Clause 7 asserting no `domain.<a>` module imports from `domain.<b>._protocols` for `a != b`, with anti-tautology proof.

## Status

BLOCKED

## Implementation

Added `find_sibling_domain_protocol_imports()` to `src/aeat/diagnostics/_identity_placement.py`.
Anti-tautology proof `test_sibling_domain_protocol_detector_flags_synthetic_violation` added.

## Blocked reason

1 production violation:

- `src/aeat/domain/filing/_schema.py:23` — imports `ModeloDraftStatus` from
  `domain.submission._protocols`. Owning wave: W06 (Protocol centralisation / MIGRATE-003).

## Commit

`8a08cac3f` — diagnostics(W11.P28): extend enforcement test to 10 clauses per Rule 11

## Files touched

- `src/aeat/diagnostics/_identity_placement.py`
- `src/aeat/diagnostics/test_identity_primitive_placement.py`
