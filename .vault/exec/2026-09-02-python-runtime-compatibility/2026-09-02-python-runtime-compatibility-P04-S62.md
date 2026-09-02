---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:958c0316a8a050da6fc38c60574841aae7d05c020ce755642ce6626f53a9b625'
step_id: 'S62'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Scope hash enforcement without rejecting locally built cohort artifacts

## Scope

- `dev/packaging/release_cohort.py`

## Changes

- `M` `dev/packaging/python_cohort.py`
- `verify:` `uv run --no-sync pytest -q -p no:randomly dev/packaging/tests/test_python_cohort_digest_assertions.py dev/packaging/tests/test_release_cohort.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/packaging/python_cohort.py` -> `pass`

## Notes

- The plan scope names `release_cohort.py` because it owns the `UV_REQUIRE_HASHES=1` policy; the local-wheel digest binding is implemented at the called `python_cohort.py` attestation seam and is recorded above as the actual modified path.
