---
name: carried-observations-stamp-their-revision
---

# Carried observations stamp their revision and re-confirm it on carry

## Rule

Every persisted calculation observation MUST carry a required, non-empty
law-determined revision stamp (`stamped_revision_id` on the observation envelope,
`src/cadrumo/application/calculations/_observations_repository.py`). A missing or
invalid stamp MUST refuse at strict load. Every cross-period / cross-year carry
MUST re-confirm a populated stamp against `select_revision` for the source context
before trusting the value; a divergent or otherwise unreconfirmable stamp MUST
block carry.

## Why

ADR `2026-06-10-period-revision-resolution-adr` (ruling 3 / R2) decided the carry
path is the one place a revision error *compounds across years*: a prior filed
under the wrong revision injects that revision's norms into every later filing
that folds it in. Stamping the revision at write time and re-confirming it at
read time makes the legal provenance enforceable. Accepting an unstamped,
invalidly stamped, divergent, or unreconfirmable observation would propagate an
ungrounded legal revision through later calculations. The pre-release cutover
therefore has no legacy compatibility path.

## How

- Good: the producer persists `stamped_revision_id` from the law-selected snapshot it
  already holds, or the repository derives that selection before constructing the
  persisted payload.
- Good: strict payload validation rejects a missing or invalid
  `stamped_revision_id`; anti-tautology coverage physically deletes the persisted
  field and proves that loading fails.
- Good: the carry gate re-confirms the populated stamp through `select_revision`; a
  match carries, while divergence or inability to resolve the source revision blocks.
- Bad: reconstructing, defaulting, or bypassing a missing persisted stamp — legal
  provenance must exist in the stored evidence itself.
- Bad: treating a divergent stamp as a warning instead of a blocker — a prior
  filed under one revision must not silently carry its norms into a period the
  law binds to another.
