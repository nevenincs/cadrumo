---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:636e135b87a7fe5eb881ff3314627f31a36d3b5364eb77571b2b7b7b80ff5ff3'
step_id: 'S97'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove censal effects, provenance, interactions and cleanup through the CLI censo production seam -- the entrypoints censal review driver reached by the censo pull verb -- using the real composed operation services. RE-HOMED from the TUI path, which has no production caller of any kind. SCOPE NARROWED against the standing goal in one respect that must not be lost: filed-history is EXCLUDED, because the filed-history pull operation has no production caller on any frontend, so its effects and provenance remain unproven end to end and still require their own Step. Everything else the original row named -- effects, provenance, interactions, cleanup -- is proven against a genuinely production-reachable seam rather than a constructed one

## Scope

- `the entrypoints test package covering the censal sync path through the real composed operation services`

## Changes

- `A` `src/cadrumo/entrypoints/tests/test_censal_sync_operations.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tests/test_censal_sync_operations.py -m integration -n0 -q` -> `pass`

## Notes

Discovery for this Step ran against the local fallback search index, not the live
semantic-search service, which was down for the session. Absence of a result in that
index is therefore not evidence that no such code exists; every claim about what does
or does not exist in the tree was confirmed by direct search of the source rather than
by the index alone.

SCOPE EXCLUSION, carried from the Step row and repeated here so a green result cannot
be read as covering it: filed-history is NOT proven. The filed-history pull operation
has no production caller on any frontend, so nothing about its effects or provenance
can be established from a frontend seam. It still requires its own Step.

SCOPE LIMIT on the seam itself. The censo pull verb calls the public censal driver
with no injected services, so the driver composes the production dependency graph
itself and the censal executor then performs a live AEAT read. That branch cannot be
driven from a test without contacting the tax authority, which is prohibited. These
cases therefore drive the same driver function the verb calls, against the production
composition function and the production registry, with acquisition bound to a local
observation. The self-composing branch of the driver remains unexercised, and no test
in the tree exercises it.

PROVENANCE IS GUARDED UPSTREAM OF THE ASSERTION, which changes what the mutation
proof shows. Three mutations were tried at three layers -- stripping the source tag
when censal facts are derived, when reviewed effects are computed, and at the record
persistence boundary itself. All three red the applying cases, but none reaches the
provenance assertion: the operation refuses to settle with its declared effect once
the attribution is wrong, at every layer reachable from outside. So production fails
closed on mis-attributed censal values rather than persisting them, and the assertion
here confirms and documents the landed contract rather than being its sole detector.
That is worth knowing before anyone treats the assertion as the guard.

The driver, the composed operation services, the supervisor, the censal executor, the
review projection and response path, and the profile record repository are all
production. The acquisition observation and the reviewed-record fixture are supplied
by the harness, which is what keeps the case off the network.
