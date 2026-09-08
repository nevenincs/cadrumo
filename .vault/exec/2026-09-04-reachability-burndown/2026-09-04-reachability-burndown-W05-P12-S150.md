---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:93e0672c808ec5c4b9b71acd3e5400cc570c5ef77757ef8d4eb3cf7c6dc8cdf6'
step_id: 'S150'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unused AEAT-local latin-1 alias and the identity-specific inventory test that required the orphan to exist; retain the shared encoding authority and the literal-survivor detector.

## Scope

- `sede browser constants and encoding inventory tests`

## Changes

- `M` `src/cadrumo/adapters/outbound/aeat/sede/_browser_constants.py`
- `M` `src/cadrumo/tests/test_hardcoded_constants_inventory.py`
- `M` `src/cadrumo/tests/test_enum_constant_extraction_inventory.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/tests/test_hardcoded_constants_inventory.py src/cadrumo/tests/test_enum_constant_extraction_inventory.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/adapters/outbound/aeat/sede/_browser_constants.py src/cadrumo/tests/test_hardcoded_constants_inventory.py src/cadrumo/tests/test_enum_constant_extraction_inventory.py` -> `pass`
- `verify:` `rg -n "SEDE_BODY_ENCODING" src dev .vault --glob '!*.pyc'` -> `pass`
- `verify:` `uv run python -c "from dev.quality.unused_symbol_coverage import run_gate; ..."` -> `pass` (377 live symbols, 20 orphan tests, alias absent)
