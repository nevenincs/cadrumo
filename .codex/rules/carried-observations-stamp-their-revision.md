---
name: carried-observations-stamp-their-revision
trigger: always_on
---

# Carried observations stamp their revision and re-confirm it on carry

## Rule

Every persisted calculation observation MUST stamp the registry revision its
source filing resolved to (`stamped_revision_id` on the observation envelope,
`src/aeat/application/calculations/_observations_repository.py`), and every
cross-period / cross-year carry read MUST re-confirm that stamp against
`select_revision` for the source context before trusting the value — a divergent
stamp blocks the carry, a missing (legacy) stamp surfaces a non-blocking
advisory, never silence.

## Why

ADR `2026-06-10-period-revision-resolution-adr` (ruling 3 / R2) decided the carry
path is the one place a revision error *compounds across years*: a prior filed
under the wrong revision injects that revision's norms into every later filing
that folds it in. The pre-ADR envelope carried no revision field, so a
stale-revision prior could not even be detected. Stamping the revision at write
time and re-confirming it at read time makes the contradiction loud; the
blocking-vs-advisory split follows `no-silent-under-declaration` — a contradicted
claim blocks, an absent legacy claim warns without bricking stored history.

## How

- Good: a producer stamps `stamped_revision_id` from the snapshot it already
  holds; the carry-read gate computes `(diverges, advisory)` —
  `payload.stamped_revision_id != snapshot.revision.id`
  (`_binding_prefill.py:98`) — and a divergent stamp yields
  `REGISTRY_REVISION_DIVERGENCE`
  (`_cross_period_clean_state.py:106`), blocking the carry.
- Good: a missing stamp on a legacy record returns `(False, True)` — the carry
  proceeds but sets `unstamped_revision_advisory`
  (`_cross_period_clean_state.py:207`, `_binding_prefill.py:88`), surfacing a
  non-blocking advisory.
- Bad: persisting an observation with no `stamped_revision_id` and trusting the
  carried value silently — the prior's revision can no longer be re-confirmed, so
  a stale-revision norm propagates undetected.
- Bad: treating a divergent stamp as a warning instead of a blocker — a prior
  filed under one revision must not silently carry its norms into a period the
  law binds to another.
