---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:cbd1124da02fb8e1893382663ae9911c27bfa96a9ea0ebd43ba428ebeb4c4d11'
step_id: 'S120'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Adjudicate the 108 unclassified modules the rebuilt load census exposed. Measured at HEAD 2026-08-30: universe 384, classified 276, 108 unclassified of which 103 are registry submodules. These were preempted rather than absent -- the old facade reader raised inside build_reference_map before the classification assertion ran. Grounded split: 80 sit INSIDE the static load closure and are live by the same evidence the existing ValidatedRegistryAuthority.load rules cite; 28 sit outside it and are the post-load public surface plus the oracle and parity tiers (snapshot, queries, coverage, handoffs, the four m303 projections, aeat_nif_iva_oracle, groi_oracle, renta_web_open_oracle, live_parity and the rest, enumerated in the audit). Do NOT close this with one bulk live rule over the 80: a bulk membership list is exactly what produced the duplicate claim on _validate_cross_revision_contiguity that the census refused. Review the 28 individually, since absence from the LOAD closure is not evidence of death for a post-load module, and re-run the census immediately before adjudicating because the package is being actively split

## Scope

- `dev/registry/analysis/load_census_classification.py`

## Changes

- `M` `dev/registry/analysis/load_census_classification.py`
- `M` `dev/registry/tests/test_load_census_classification.py`
- `verify:` `uv run --no-sync pytest -q dev/registry/tests/test_load_census_classification.py` -> pass
- `verify:` `uv run --no-sync ruff check dev/registry/analysis/load_census_classification.py dev/registry/tests/test_load_census_classification.py` -> pass

## Notes

- `uv run --no-sync python -m dev.registry.analysis.load_census --trace --json` remains blocked before its warm trace by the peer-owned in-flight `src/cadrumo/domain/calculations/registry/schema_scalars.py:319` `NameError` for `SPANISH_PROVINCE_CODE_PATTERN`; no workaround was introduced in this step.
