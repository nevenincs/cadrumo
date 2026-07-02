---
tags:
  - '#exec'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S11'
related:
  - '[[2026-07-02-arch-remediation-gates-ratchet-plan]]'
---

# Add domain-to-adapters count ratchet

## Scope

- `src/aeat/tests/test_importlinter_ledger.py`

## Description

- Added a layered-contract count ratchet for domain-to-adapters ignore edges.
- Used the post-repair ledger as the baseline so later port-inversion work can only reduce the count.

## Outcome

The domain-to-adapters layered baseline is 70 ignore edges.

## Notes

The test is a ledger-structure check only; it pins existing coupling and does not refactor production imports.
