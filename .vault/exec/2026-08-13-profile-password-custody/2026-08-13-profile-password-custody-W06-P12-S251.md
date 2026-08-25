---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:71bb65667b2f038408672c1dd55a4a36b9b676e6cc06ce8c3af8a5b7a4f94169'
step_id: 'S251'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Repair filing-spine cumulative state so reused seed identity resolves the latest draft target and its documentation sequence proves the intended state transition

## Scope

- `docs/_sequences/contracts/filing-spine/ and src/cadrumo/application/`

## Description

- Trace latest-state selection through `select_modelo_calculation_revision` and `_latest_revision_with_state` before changing the documentation contract.
- Preserve the application selector as the sole authority for `latest-draft`, `latest-verified`, and `filed` resolution.
- Change cumulative filing-spine examples to produce distinct content-addressed revisions before advancing their lifecycle.
- Assert that one captured revision identity moves through draft, verified, and filed states.
- Replace cumulative-state-dependent history and run counts with stable operation and target assertions.
- Regenerate the filing-spine page goldens through the sequence owner CLI.

## Outcome

The cumulative page now demonstrates immutable revision semantics honestly: changed ledger input creates a new draft, and the same captured revision is selected after each lifecycle transition. Downstream history and run-list examples remain valid after prior page actions without duplicating application resolution logic.

## Notes

- Governing ADR research ruled out changing the application selector merely to make a reused, already-filed content hash appear draft again.
- Concurrent commit `8b79ffd895a` captured the contract edits and three generated goldens while this Step was still executing; the Step closure cites that provenance rather than claiming a single isolated implementation commit.
- Focused verification was temporarily interrupted by a concurrent operation-persistence relocation in the shared worktree and resumed after that peer work settled.
- Verification passed: filing-spine golden and cumulative coherence checks; 15 selector tests; 61 parser/comparator tests; 349 documented-command conformance tests; scoped Ruff and ty checks.
