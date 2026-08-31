---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7d19dfce190fbf33a9537cd447fdafb58f04677a70dacdcaff3cb54292daab2c'
step_id: 'S143'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Refactor the size-budget subjects in _producer_snapshot.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/filing/_producer_snapshot.py`

## Changes

- `M` `src/cadrumo/application/filing/_producer_snapshot.py`
- `A` `src/cadrumo/application/filing/_producer_snapshot_m200.py`
- `A` `src/cadrumo/application/filing/_producer_snapshot_m390.py`
- `M` `src/cadrumo/application/filing/_m200_projection.py`
- `M` `src/cadrumo/application/filing/_export_producer.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/filing/_producer_snapshot.py src/cadrumo/application/filing/_producer_snapshot_m200.py src/cadrumo/application/filing/_producer_snapshot_m390.py src/cadrumo/application/filing/_m200_projection.py src/cadrumo/application/filing/_export_producer.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n 0 -o addopts= --collect-only -q src/cadrumo/application/filing/tests/test_export_value_policy.py src/cadrumo/application/filing/tests/test_export_post_write_verification.py src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n 0 -o addopts= -q src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py` -> `pass`
