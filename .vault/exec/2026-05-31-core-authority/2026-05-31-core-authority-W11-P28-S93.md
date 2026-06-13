---
step_id: S93
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W11.P28.S93 step record

## Step

Implement Clause 6 asserting no `domain.<a>` module imports from `domain.<b>._constants` for `a != b`, with anti-tautology proof.

## Status

DONE

## Implementation

Fixed clause-6 violation:
- `src/aeat/domain/buckets/_event.py:24` — changed from
  `from ..profile._constants import ProfileName as _ProfileName` to
  `from ..profile import ProfileName as _ProfileName` (public surface import).

`ProfileName` is already exported through `domain/profile/__init__.py`.

Zero-violation assertion `test_no_sibling_domain_constant_imports` added to
diagnostics test in S95 commit.

## Action class

MOVE (import path correction — no symbol relocation required)

## Commits

- `aded66ecf` — exec(core-authority): W11.P28.S93 clause-6 sibling-domain _constants fix

## Files touched

- `src/aeat/domain/buckets/_event.py`
- `src/aeat/diagnostics/test_identity_primitive_placement.py` (clause-6 zero-violation test added in S95)
