---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:58474b30f15fa49f4e5da575dbe0880f8920a4d72b709b390fb870270fa13437'
step_id: 'S49'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Remove the repeated passes the cohort build makes over artifacts it has already produced

## Scope

- `dev/packaging/python_cohort.py`

## Changes

- `M` `dev/packaging/python_cohort.py`
- `M` `dev/packaging/runtime_wheelhouse.py`
- `M` `dev/packaging/release_cohort.py`
- `M` `dev/packaging/build_scratch_reclaim.py`
- `A` `dev/packaging/tests/test_var_scratch_mint_sites_are_registered.py`
- `M` `dev/packaging/tests/test_python_cohort.py`
- `M` `dev/packaging/tests/test_runtime_wheelhouse.py`
- `M` `dev/packaging/tests/test_release_cohort_integration.py`
- `M` `dev/packaging/tests/test_build_scratch_reclaim.py`
- `M` `packaging/scoop/tests/test_scoop_generate.py`
- `M` `packaging/homebrew/tests/test_homebrew_generate.py`

## Notes

The cohort's artifacts are byte-reproducible only under the release path's
environment stamp. A parity build without it produced identical member
listings with sizes differing by one to several hundred bytes -- archive
timestamps, not content. Under the stamp the release build sets, all eight
digests match the reference. This is a property of the builder rather than a
defect, and is recorded because a future parity check run bare will look
broken and is not.

Five failures remain in the packaging suites, all one root cause and all
predating this work: the runtime wheelhouse is a required manifest key, and
three hand-assembled cohort fixtures never add one, so the loader refuses on
drifted keys. The helper those fixtures need already exists.

## Scope

- `dev/packaging/python_cohort.py`

## Changes

- `M` `dev/packaging/python_cohort.py`
- `M` `dev/packaging/runtime_wheelhouse.py`
- `M` `dev/packaging/release_cohort.py`
- `M` `dev/packaging/tests/test_python_cohort.py`
- `M` `dev/packaging/tests/test_release_cohort.py`
- `M` `dev/packaging/tests/test_installed_oracles.py`
- `M` `packaging/scoop/tests/test_scoop_generate.py`
- `M` `packaging/homebrew/tests/test_homebrew_generate.py`

## Scope

- `dev/packaging/python_cohort.py`

## Changes
