---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:00d3f5d7bfcd14af296cfaabff83db99588ee57ec5c1a58fd6f85753c32a7bcd'
step_id: 'S122'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Refactor the size-budget subjects in calc_sheets_apply.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/adapters/outbound/google/calc_sheets_apply.py`

## Changes

- `M` `src/cadrumo/adapters/outbound/google/calc_sheets_apply.py`
- `A` `src/cadrumo/adapters/outbound/google/_calc_sheets_apply_formatting.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_apply_adapter_helpers.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_export_integration.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_offline_online_conformance.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_transport_facet_parity.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_grid_resize.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_package_module_allowlist.py`
- `verify:` `uv run --no-sync pytest -n0 -q <five focused real Modelo-plan builder modules>` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -q <apply/preview/clear-order consumer modules>` -> `pass`
- `verify:` `uv run --no-sync ruff check <S122 paths> && uv run --no-sync ruff format --check <S122 paths>` -> `pass`
- `verify:` `source-specific size measurement for calc_sheets_apply.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.size_budget` -> `fail`

## Notes

Grounded against predecessor `6df9635e34`. The source-specific ratchet measurement is 1,172 lines against the default 1,250-line limit. The canonical global size gate exits 1 with 92 remaining findings owned by still-open P05 rows; `calc_sheets_apply.py` is absent from that output. No baseline was changed.
