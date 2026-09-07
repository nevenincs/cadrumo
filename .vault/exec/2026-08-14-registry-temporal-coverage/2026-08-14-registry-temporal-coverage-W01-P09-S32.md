---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:260b5e0e40c9596774ea943b95ae3d1b686e1a310e029881d12a380d8bf7d2d8'
step_id: 'S32'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---
# Reconcile the already-landed property-based Modelo 303 semantic-map census that discovers every authored design epoch dynamically, then extend temporal drift detection beyond year-token filenames to module-level literal (modelo, revision) enrolment collections. Derive the expected universe from the canonical law-selected temporal projection, require every exclusion to be an explicit source-digest-bound per-subject pin that goes dormant on reissue, and prove detector teeth with isolated yearless fixtures whose removed or altered pair reports the exact missing or extra identity without frozen corpus counts or double-counting imported collections.

## Scope

- `dev/registry/analysis/temporal_enrollment_census.py`
- `dev/registry/tests/test_temporal_enrollment_census.py`
- `dev/registry/analysis/m303_semantic_census.py`
- `dev/registry/tests/test_modelo_303_semantic_maps.py`

## Changes

- `A` `dev/registry/analysis/temporal_enrollment_census.py`
- `A` `dev/registry/tests/test_temporal_enrollment_census.py`
- `verify:` `uv run python -u -m pytest -q dev/registry/tests/test_temporal_enrollment_census.py dev/registry/tests/test_modelo_303_semantic_maps.py::test_every_authored_design_epoch_is_discoverable_and_reviewed dev/registry/tests/test_modelo_303_semantic_maps.py::test_the_reviewed_epoch_chain_reaches_every_epoch_from_one_root src/cadrumo/domain/calculations/registry/tests/test_revision_span_boundaries.py::test_no_revision_spans_a_design_relayout` -> `pass`
- `verify:` `uv run ruff check dev/registry/analysis/temporal_enrollment_census.py dev/registry/tests/test_temporal_enrollment_census.py` -> `pass`
- `verify:` `uv run basedpyright dev/registry/analysis/temporal_enrollment_census.py dev/registry/tests/test_temporal_enrollment_census.py` -> `pass`
