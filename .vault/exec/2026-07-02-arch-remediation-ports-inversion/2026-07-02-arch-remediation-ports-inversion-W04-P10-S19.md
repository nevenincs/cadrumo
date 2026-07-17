---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S19'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Assert zero production domain-to-adapters pinned entries remain in the ledger via the count-ratchet gate landed by the gates-ratchet campaign

## Scope

- `.importlinter`

## Description

- Assert zero production `domain -> adapters` pinned entries remain in the importlinter ledger now that every domain repository sits behind a port.
- Add `test_zero_production_domain_to_adapters_edges` to the ledger gate: it scans every contract's ignore edges, filters out test-file sources (`.tests.` / `.conftest`), and asserts the remaining production `domain.* -> adapters.*` set is empty — a hard zero, not a ratchet.
- Keep the existing `test_domain_to_adapters_pin_count_does_not_grow` ratchet for the test-edge total.

## Outcome

Complete in commit `be5ca85b22`. Grep of the ledger confirms zero production `domain.* -> adapters.*` edges; the new gate passes (ledger test 4/4 green). `lint-imports` shows no `domain -> adapters` violation anywhere in the broken layered output (the layered breakage is the pre-existing, separately-tracked application -> adapters wiring). A production domain -> adapters edge reappearing now fails this gate loudly rather than being absorbed as an ignore.

## Notes

Landed together with S20 in the same closeout commit `be5ca85b22` (both edit `.importlinter`; S19 also edits the ledger test). Committed with an explicit pathspec verified via `git diff --cached` before commit.
