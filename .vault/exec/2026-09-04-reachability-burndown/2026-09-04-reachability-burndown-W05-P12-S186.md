---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:2f1d9c566d2833b6988df6201c1b6b55204363fef8cea9e696e3eafd0f595530'
step_id: 'S186'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the two test-only filed-declaration binding and relation resolver wrappers from declarations_observations, migrate their tests to the canonical domain resolvers through registry_observation_from_filed_declaration, and retain the live application filed-state ownership path.

## Scope

- `declarations observation facade`
- `binding/relation tests`
- `canonical application/domain resolver ownership`
- `live reachability measurement`

## Changes

- `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations_observations.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/_declarations_support.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part2.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part3.py`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part3.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part2.py::TestFiledObservationBindings` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/outbound/aeat/sede/declarations_observations.py src/cadrumo/adapters/outbound/aeat/sede/tests/_declarations_support.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part2.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part3.py` -> `pass`

## Notes

The broader Modelo 130 submitted-file test remains red before resolver invocation because concurrent registry work makes its signed casilla fixture fail fixed-width parsing; the canonical prior-filing and relation resolver selections pass independently.
