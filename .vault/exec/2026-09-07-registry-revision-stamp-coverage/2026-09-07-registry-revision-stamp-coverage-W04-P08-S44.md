---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:eecbaade4f5c39274a22ee0ed2e60aa702cd430bd55d1f3e643c8fa6a79472ff'
step_id: 'S44'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Run focused unit and secure-persistence round-trip suites for every migrated carrier

## Scope

- `src/cadrumo`

## Changes

- `verify:` `uv run pytest -q -n0 dev/quality/tests/test_registry_revision_stamp_coverage.py` -> `pass`
- `verify:` `uv run pytest -q -n0 <calculation, Borrador, filing, export, review, reconciliation, advisory, and declarations divergence suites>` -> `pass`
- `verify:` `uv run pytest -q -n0 <nine secure-persistence and carrier round-trip suites>` -> `pass`
- `verify:` `uv run pytest -q -n0 <M303 canonical ingress, wallet, observation, operator, and prorrata suites>` -> `pass`

## Notes

The secure-persistence selection passed 108 tests before three stale fixture
expectations failed; after canonical migration, those three selectors passed.
The M303 selection passed 34 tests before one registry-directory fingerprint
race caused a failure; the exact stale-stamp case passed on an isolated retry.
No campaign behavior failure remained.
After formal review remediation, the M145/amendment selection passed 99 tests,
the review/repository selection passed 44 tests, the cross-period selection
passed 31 tests, and the final canonical carry-fixture selection passed 9 tests.
