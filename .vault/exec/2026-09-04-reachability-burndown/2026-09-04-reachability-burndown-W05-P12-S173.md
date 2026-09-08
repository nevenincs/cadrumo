---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:12f5660f7cf194312740603748350f8edb2dc953bd439bb73917225a3375e7cc'
step_id: 'S173'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the whole-corpus supported-filing-year gap worklist and advisory-only API from the shipped registry authority, relocate the derivation to the development coverage reporter, preserve its 888-row live output and the actual filing-boundary refusal, strengthen the production-metastate detector for review residue attached to product authorities, and correct the temporal-coverage ADR ownership.

## Scope

- `src/cadrumo/domain/calculations/registry/_supported_filing_years.py and authority.py`
- `registry tests`
- `dev/registry/supported_filing_years.py and coverage residue reporter`
- `production-metastate gate and teeth`
- `registry-temporal-coverage ADR`
- `reachability burndown reference`
- `focused registry and dev coverage gates`
- `live unused-symbol measurement`

## Changes

- `D` `src/cadrumo/domain/calculations/registry/_supported_filing_years.py`
- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_filing_bound_cell_advisories.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_supported_filing_years_catalogue.py`
- `A` `dev/registry/supported_filing_years.py`
- `M` `dev/registry/analysis/coverage_residue_worklist.py`
- `M` `dev/quality/production_metastate.py`
- `M` `dev/quality/tests/test_production_metastate.py`
- `M` `.vault/adr/2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "SupportedFilingYearGap|audit_supported_filing_years|supported_filing_year_gaps|filing_bound_advisories_for_cell" src/cadrumo -g "*.py"` -> `pass`
- `verify:` `uv run ruff check <S173 Python paths>` -> `pass`
- `verify:` `uv run pytest -q -n0 src/cadrumo/domain/calculations/registry/tests/test_authority.py` -> `pass` (11 passed)
- `verify:` `uv run pytest -q -n0 src/cadrumo/domain/calculations/registry/tests/test_supported_filing_years_catalogue.py dev/registry/tests/test_temporal_coverage.py` -> `pass` (48 passed)
- `verify:` `uv run pytest -q dev/quality/tests/test_production_metastate.py dev/quality/tests/test_suite_gate_table.py` -> `pass` (13 passed)
- `verify:` `uv run python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run python -m dev.registry.analysis.coverage_residue_worklist` -> `pass` (888 live residue cells)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail`

## Notes

The live unused-symbol detector remains at 360 exact symbols and 18 orphan test modules; this Step removes derived development state from production rather than an exact-symbol row. The deleted production advisory API had no production caller. The development reporter continues to derive the same review worklist directly from canonical authority models and catalogues.
