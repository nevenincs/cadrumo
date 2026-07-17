---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S42'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Verify cohort hashes evidence completeness and destination versions before any upload

## Scope

- `dev/release/promote_python_cohort.py`

## Description

- Read `validate_promotion`, `assert_pypi_destinations_absent`, and `load_python_cohort` to understand the full validation surface.
- Authored `dev/release/tests/test_promote_python_cohort.py` with six unit tests and one integration-marked test.
- Built minimal real wheel (zip) and sdist (gzip tarball) helpers that pass `_validate_wheel_contract` and `_validate_sdist_contract` without a full build pipeline.
- Implemented `_make_cohort_dir` to write a valid `python-cohort.json` manifest with correct SHA-256 digests computed from the artifacts on disk.
- Verified that marking tests individually (not via module-level `pytestmark`) is required because the integration test cannot carry the `unit` marker.
- Fixed a ruff B015 warning on the integration test return value assertion.
- Ran `ruff check`, `ruff format --check`, and `ty check` clean on the new file.
- Confirmed 6/6 unit tests pass and 7/7 sibling `test_distribution_readiness.py` tests remain green.
- Committed as `448aedc16a` with explicit pathspec.

## Outcome

Six unit tests cover the five required behaviors:
(1) a complete valid cohort and evidence pair passes `validate_promotion`;
(2) a tampered artifact digest in the evidence document is refused;
(3) a missing `cli_oracle` key is refused;
(4) a missing `mcp_oracle` key is refused;
(5) a wrong `expected_source_commit` is refused;
(6) evidence produced from byte-distinct artifacts (destination-version mismatch) is refused.

The integration-marked test exercises `assert_pypi_destinations_absent` with a real `PythonCohort` dataclass instance and a dev version guaranteed absent from PyPI.

## Notes

The PyPI pre-upload guard refusal path (version already published) cannot be tested in unit scope: the function makes unconditional live HTTP calls and exposes no network seam. The integration test covers the happy path (version absent, function returns without raising). The already-published path is noted as a known limitation in the test module docstring.
