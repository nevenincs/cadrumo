---
tags:
  - '#plan'
  - '#test-clave-movil-mark-fix'
date: '2026-04-27'
related:
  - '[[2026-04-27-test-clave-movil-mark-fix-research]]'
  - '[[2026-04-27-test-clave-movil-mark-fix-adr]]'
---

# `test-clave-movil-mark-fix` implementation plan

This plan implements the accepted Path A decision: align the Cl@ve Movil authentication test module with the live-read marker taxonomy and remove any stale ignore workaround references.

## Proposed Changes

Update `src/aeat/auth/test_clave_movil.py` so the whole module is marked `live_read` and `domain_aeat_remote`.

Document at the top of the file that these tests are operator-enabled through `AEAT_LIVE_TESTS_ENABLED=1`.

Use the shared live-test helper to ensure explicit source-only live selection skips when the opt-in flag is false.

Confirm that the searched workaround surfaces contain no remaining `--ignore=src/aeat/auth/test_clave_movil.py` references.

## Tasks

- Update the module marker and docstring.
- Add the shared live opt-in guard if direct source-only collection is not otherwise gated.
- Search the repository workaround surfaces for stale ignore references.
- Verify default unit selection, explicit live selection with opt-in disabled, and explicit live selection with opt-in enabled.
- Run lint, typecheck, unit tests, coverage, hooks, and code review.

## Parallelization

This is a narrow single-file source change plus vault records. Parallel execution is useful only for independent searches and verification commands.

## Verification

Success means the module no longer appears in default unit selection, explicit `live_read` selection does not run accidentally without opt-in, and opt-in execution still collects and runs the tests. The source diff must not touch `_clave_movil.py` or any AEAT submission surface.
