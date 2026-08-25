---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:69d70cb5630546374a6f604f5fce84bd72da556d9832578b9d91ad2d27229a49'
step_id: 'S269'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Move the documentation sequence runner to the canonical relocated profile-capsule runtime helper and repair its ownership link without recreating the retired test facade

## Scope

- `dev/docs/sequences/_runner.py and cadrumo/adapters/persistence/storage/tests/profile_capsule_runtime.py`

## Description

- Located the production capsule lifecycle and relocated runtime helper through Vaultspec RAG, then confirmed the retired runner reach and canonical defining symbol with exact source search.
- Rewired the documentation sequence runner to import `publish_test_profile_capsule` from its canonical persistence test-runtime owner and corrected the public ownership link in the runner documentation.
- Added a real regression that proves object identity with the canonical helper and opens an encrypted sequence sandbox whose deterministic profile capsule exists at the production bucket path.
- Proved the retired facade is no longer reached and exercised the full main nitpicky build through initialization and complete output traversal.

## Outcome

The sequence runner now composes the relocated capsule runtime directly. It does not redeclare the helper or restore an export on the retired `cadrumo.tests.profile_capsule` facade. A real sandbox publication passes, and the full documentation build advances through all sources and output instead of failing at `builder-inited`.

Verification:

- `uv run pytest -q -n 0 -m integration dev/docs/sequences/tests/test_runner.py::test_sandbox_publishes_through_canonical_capsule_runtime` - 1 passed in 42.50 seconds.
- `uv run ruff check dev/docs/sequences/_runner.py dev/docs/sequences/tests/test_runner.py src/cadrumo/adapters/persistence/storage/tests/profile_capsule_runtime.py` - passed.
- `uv run ty check dev/docs/sequences/_runner.py src/cadrumo/adapters/persistence/storage/tests/profile_capsule_runtime.py` - passed.
- Canonical import identity and retired-facade search gate - passed.
- `uv run pytest -q -n 0 -m unit dev/docs/tests/test_docs_build_full_scope.py` - initialization and full traversal succeeded; terminal result remains red with 70 S268-owned nitpicky warnings after 664.54 seconds, with no capsule import or sequence-runner failure.
- Formal read-only review - APPROVE with no findings at any severity; the reviewer confirmed canonical ownership, real encrypted publication, and no wrapper, alias, redeclaration, or bypass.

## Notes

The first exact pytest invocation inherited the repository unit-only marker expression and honestly deselected the integration test; it was rerun with `-m integration`. Whole-file ty reports existing diagnostics in unrelated portions of `test_runner.py`; the changed implementation paths are clean, and the new test is runtime-proven. The shared worktree contained concurrent S268 documentation work and peer source/plan work; this step's commit is restricted to its explicit runner, regression, plan row if still uncommitted, execution record, and generated profile-password-custody index if changed by the owning CLI.
