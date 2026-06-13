---
tags:
  - '#exec'
  - '#p2e-tax-category-catalogue'
date: '2026-04-13'
modified: '2026-04-13'
related:
  - '[[2026-04-13-p2e-tax-category-catalogue-research]]'
  - '[[2026-04-13-p2e-tax-category-catalogue-adr]]'
  - '[[2026-04-13-p2e-tax-category-catalogue-plan]]'
  - '[[2026-04-13-p2e-tax-category-catalogue-review-audit]]'
---

# `p2e-tax-category-catalogue` `phase-1` summary

Execution record for issue `#77`, TDP step `T4`. Scope is the strict
spending-category taxonomy substrate only: the category enum, profile models,
proportionality rules, coarse casilla mappings, registry, loader, CLI, and
unit-test coverage. Runtime evaluators and downstream classifiers remain out of
scope for `#78`, `#79`, `#85`, `#87`, and `#91`.

## Tasks executed

- Added `src/aeat/domain/financial/__init__.py` and the new
  `src/aeat/domain/financial/categories/` public package.
- Landed strict/frozen pydantic v2 boundary models for:
  - `Citation`
  - `ProportionalityRule`
  - `CasillaMapping`
  - `CategoryProfile`
- Added closed `StrEnum` catalogues for:
  - `SpendingCategory`
  - `SpendingCategoryFamily`
  - `ProportionalityKind`
  - `CasillaMappingSign`
  - local `VatCategory` hint stub
- Added the additive casillas enum surface required by the new package:
  - `aeat.domain.casillas.ModeloCode`
  - `aeat.domain.casillas.PeriodType`
- Implemented `CATEGORY_PROFILES_2025` as a frozen 38-category registry with:
  - trilingual display labels
  - per-category proportionality profiles
  - mandatory citations on every rule
  - coarse `MODELO_130` and `MODELO_303` mappings
  - conservative notes where the requested category label is broader than the
    strongest 2025 handbook wording
- Implemented `load_category_profiles_from_manual(year: int)` as the
  manual-aware loader with deterministic fallback to the curated registry.
- Added `aeat categories` CLI support:
  - `aeat categories list`
  - `aeat categories show <category>`
  - `aeat categories casillas <modelo>`
- Added colocated unit tests for:
  - enum/family coverage
  - profile validation
  - proportionality validation
  - registry completeness and citation integrity
  - casilla mapping integrity against committed `aeat.domain.casillas` data
  - CLI behavior

## Files changed

- `src/aeat/domain/casillas/__init__.py`
- `src/aeat/domain/casillas/models.py`
- `src/aeat/entrypoints/cli/__init__.py`
- `src/aeat/entrypoints/cli/categories.py`
- `src/aeat/entrypoints/cli/test_categories_cli.py`
- `src/aeat/domain/financial/__init__.py`
- `src/aeat/domain/financial/categories/__init__.py`
- `src/aeat/domain/financial/categories/_casilla_mapping.py`
- `src/aeat/domain/financial/categories/_corpus.py`
- `src/aeat/domain/financial/categories/_profile.py`
- `src/aeat/domain/financial/categories/_proportionality.py`
- `src/aeat/domain/financial/categories/_registry.py`
- `src/aeat/domain/financial/categories/_spending_category.py`
- `src/aeat/domain/financial/categories/test_profile.py`
- `src/aeat/domain/financial/categories/test_proportionality.py`
- `src/aeat/domain/financial/categories/test_registry.py`
- `src/aeat/domain/financial/categories/test_spending_category.py`

## Verification

Executed on Windows in this worktree on `2026-04-13`:

- `uv sync --all-groups --upgrade`
- `uv lock --upgrade`
- `uv run vaultspec-core install --upgrade`
- `uv run pytest src/aeat/domain/financial/categories src/aeat/entrypoints/cli/test_categories_cli.py -q`
- `just lint`
- `just typecheck`
- `just test`
- `just hooks`

Results:

- Focused category + CLI slice: `16 passed`
- Full repo suite: `761 passed, 1 skipped, 24 deselected`
- `just lint`: clean
- `just typecheck`: clean
- `just hooks`: clean

## Notes

- `MODELO_303` mappings remain intentionally coarse because current main does
  not expose a fine-grained deductible-input expense surface through the public
  `aeat.domain.casillas` corpus.
- The manual loader currently uses the structured manual corpus as a readiness
  check and then returns the curated registry; the public API is therefore
  stable now and can absorb richer manual extraction later without changing the
  downstream T4 contract.
