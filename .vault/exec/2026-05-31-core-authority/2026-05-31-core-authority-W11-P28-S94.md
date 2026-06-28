---
step_id: S94
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W11.P28.S94 step record

## Step

Implement Clause 7 asserting no `domain.<a>` module imports from `domain.<b>._protocols` for `a != b`, with anti-tautology proof.

## Status

DONE

## Implementation

Fixed clause-7 violation:
- `src/aeat/domain/filing/_schema.py:23` — changed from
  `from ..submission._protocols import ModeloDraftStatus` to
  `from ..submission import ModeloDraftStatus` (public surface import).

`ModeloDraftStatus` is already exported through `domain/submission/__init__.py`.

Zero-violation assertion `test_no_sibling_domain_protocol_imports` added to
diagnostics test in S95 commit.

## Action class

MOVE (import path correction — no symbol relocation required)

## Commits

- `fc96b9bdd` — exec(core-authority): W11.P28.S94 clause-7 sibling-domain _protocols fix

## Files touched

- `src/aeat/domain/filing/_schema.py`
- `src/aeat/diagnostics/test_identity_primitive_placement.py` (clause-7 zero-violation test added in S95)
