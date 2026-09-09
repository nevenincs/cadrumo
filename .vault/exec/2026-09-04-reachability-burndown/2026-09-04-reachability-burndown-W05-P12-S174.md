---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:0b4d72c452399191b501d8564993744404a875dfdf46c1b275cc8db3e12980ea'
step_id: 'S174'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unused sectoral retención-rate classifier surface that production explicitly labelled declared but unreached, retain the canonical legal-parameter authority and active consumers, amend the contradicted calculation-chain decision, and extend the aggregated production-metastate detector across module and nested executable docstrings with discriminating teeth.

## Scope

- `retención parameter API`
- `calculation-chain integrity ADR`
- `production-metastate gate and detector teeth`
- `reachability burndown reference`
- `focused domain tests`
- `live unused-symbol measurement`

## Changes

- `M` `src/cadrumo/domain/transactions/retencion_parameters.py`
- `M` `dev/quality/production_metastate.py`
- `M` `dev/quality/tests/test_production_metastate.py`
- `M` `.vault/adr/2026-08-07-calculation-chain-integrity-activity-type-placement-adr.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "sectoral_activity_retencion_rates" src/cadrumo dev -g "*.py"` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/transactions/retencion_parameters.py dev/quality/production_metastate.py dev/quality/tests/test_production_metastate.py` -> `pass`
- `verify:` `uv run pytest dev/quality/tests/test_production_metastate.py src/cadrumo/domain/transactions/tests/test_retencion_parameters.py -q -k "not shipped_production_has_no_development_metastate"` -> `pass` (15 passed)
- `verify:` `uv run python -m dev.quality.production_metastate` -> `fail` (six newly exposed live findings)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (359 exact symbols; 18 orphan test modules)

## Notes

The selected exact unused symbol is absent after deletion, reducing the exact live signal from 360 to 359 while the orphan population remains 18. The legal parameters and their active loader, statutory set, professional set, legal-reference disclosure, and inference ceiling remain. The strengthened zero-target metastate gate reports six previously hidden peer declarations, including a module-level prorrata status; those findings remain live for subsequent Steps and were not suppressed.
