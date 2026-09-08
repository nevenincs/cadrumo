---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:276acba1552894e5c84e42081400d7fd8c9b6821dd5da36339a98a29977cfdb3'
step_id: 'S138'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the registry load-census live/conditionally-reachable/dead classification table and its table-driven claim verifier, retaining only mechanically derived closure, reference, and dynamic-import signals with detector-teeth tests

## Scope

- `development load census`
- `classification and claim-verification modules`
- `tests`
- `and live graph signal`

## Changes

- `M` `dev/registry/analysis/load_census.py`
- `D` `dev/registry/analysis/load_census_classification.py`
- `D` `dev/registry/analysis/load_claim_verification.py`
- `R` `dev/registry/tests/test_load_census_classification.py` -> `dev/registry/tests/test_load_census.py`
- `D` `dev/registry/tests/test_load_claim_verification.py`
- `verify:` `uv run --no-sync ruff check dev/registry/analysis/load_census.py dev/registry/tests/test_load_census.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 dev/registry/tests/test_load_census.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.registry.analysis.load_census` -> `pass`

## Notes

The live census derives 194 registry modules and reports zero unreferenced registry candidates and zero unresolved registry-local dynamic imports. Six dynamic sites outside the registry remain visible in the report and belong to their respective owners.
