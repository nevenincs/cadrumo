---
step_id: S93
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W11.P28.S93 step record

## Step

Implement Clause 6 asserting no `domain.<a>` module imports from `domain.<b>._constants` for `a != b`, with anti-tautology proof.

## Status

BLOCKED

## Implementation

Added `find_sibling_domain_constant_imports()` to `src/aeat/diagnostics/_identity_placement.py`.
Anti-tautology proof `test_sibling_domain_constant_detector_flags_synthetic_violation` added.

## Blocked reason

1 production violation:

- `src/aeat/domain/buckets/_event.py:24` — imports `ProfileName` from
  `domain.profile._constants`. Owning wave: W03 (constant centralisation) or W04.

## Commit

`8a08cac3f` — diagnostics(W11.P28): extend enforcement test to 10 clauses per Rule 11

## Files touched

- `src/aeat/diagnostics/_identity_placement.py`
- `src/aeat/diagnostics/test_identity_primitive_placement.py`
