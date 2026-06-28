---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `phase5` `step23`

Removed rental-domain filing target authority and retained only factual rental
aggregate behaviour.

- Modified: `src/aeat/domain/rental/_aggregates.py`
- Deleted: `src/aeat/domain/rental/anexo_c_provider.py`
- Modified: `src/aeat/domain/rental/__init__.py`
- Modified: `src/aeat/domain/rental/_errors.py`
- Modified: `src/aeat/domain/rental/_models.py`
- Modified: `src/aeat/domain/rental/_enums.py`
- Modified: `src/aeat/domain/rental/_expense_rollup.py`
- Modified: `src/aeat/domain/rental/_tier_resolver.py`
- Modified: `src/aeat/core/errors/registry/_domain.py`
- Added: `tests/import_contract/domain/rental/_test_aggregates.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The rental aggregate module is now neutral: it exposes
`RentalAggregates` and `compute_rental_aggregates`, with fields for factual
rental income, deductible expenses, amortization, residential rental reduction,
and real-estate imputation. Modelo and filing-line mappings remain outside the
rental domain and must be owned by registry-backed modelo definitions.

The passthrough provider was deleted. Runtime exports no longer expose a
caller-supplied merge surface, old provider constants, or filing-line override
reports. Rental docstrings were cleaned so the package describes records,
ledger behaviour, and calculations without embedding filing target metadata.

Rental tests now assert factual aggregate behaviour through persisted
repositories and neutral aggregate outputs.

## Tests

- `uv run pytest src/aeat/domain/rental tests/import_contract/domain/rental -q`
- `uv run ruff check src/aeat/domain/rental tests/import_contract/domain/rental`
- `uv run ty check src/aeat/domain/rental tests/import_contract/domain/rental`
