---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:cd1b936f12d73535001691e436cd38d474ac7d3a7c1c17262b4a3697bf98b4e5'
step_id: 'S183'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only is_forbidden_censal_landing boolean narrowing and migrate its no-write proofs to the marker-returning authority the live refusal consumes, preserving exact offending-marker evidence instead of maintaining a second predicate vocabulary.

## Scope

- `censal landing marker authority`
- `no-write conformance tests and live reachability measurement`

## Changes

- `M` `src/cadrumo/adapters/outbound/aeat/sede/censal_datos.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_censal_no_write_surface.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_censal_datos.py`
- `verify:` `rg -n "\\bis_forbidden_censal_landing\\b" src/cadrumo dev -g "*.py"` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/outbound/aeat/sede/tests/test_censal_no_write_surface.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_censal_datos.py` -> `pass` (58 passed)
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/outbound/aeat/sede/censal_datos.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_censal_no_write_surface.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_censal_datos.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail` (349 exact symbols; 18 orphan test modules)
