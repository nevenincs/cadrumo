---
tags:
  - "#plan"
  - "#p2e-tax-category-catalogue"
date: "2026-04-13"
modified: '2026-04-13'
related:
  - "[[2026-04-13-p2e-tax-category-catalogue-research]]"
  - "[[2026-04-13-p2e-tax-category-catalogue-adr]]"
---

# `p2e-tax-category-catalogue` `phase-1` plan

Ship a strict pydantic v2 category substrate under `aeat.domain.financial.categories`
with an AEAT-aligned spending-category enum, per-category proportionality
profiles, citation-backed notes, coarse casilla mappings for current main, and a
manual-corpus fallback loader.

Topic: the T4 spending-category taxonomy substrate for 2025.

Audit surface: `#77`, `#104`, `aeat.domain.casillas`, `aeat.domain.manuals`,
`aeat.domain.normatives`, `aeat.core.i18n`, the root CLI, and the new
`aeat.domain.financial.categories` package.

Rewrite scope: new feature package, additive CLI wiring, additive casillas enums
required by the new package, and the matching vault exec/audit trail.

## Proposed changes

- Create `src/aeat/domain/financial/categories/` with the strict public model surface.
- Re-export the package at `aeat.domain.financial.categories`.
- Add the frozen `CATEGORY_PROFILES_2025` registry with complete coverage for
  every category enum value.
- Add the manual-corpus fallback loader.
- Add `aeat categories list`, `show`, and `casillas`.
- Add colocated unit tests for completeness, strictness, citations, and casilla
  mapping integrity.

## Tasks

- `phase-1-foundation`
  1. Create `src/aeat/domain/financial/__init__.py` and
     `src/aeat/domain/financial/categories/__init__.py`.
  1. Add the strict model modules:
     `_spending_category.py`, `_proportionality.py`, `_profile.py`,
     `_casilla_mapping.py`.
  1. Reuse `aeat.domain.casillas.ModeloCode` and add the minimum additive casillas enum
     surface if it does not yet exist on current main.
- `phase-1-registry`
  1. Add `_registry.py` with a complete 2025 frozen mapping.
  1. Encode current-main `MODELO_130:01` as the direct expense sink.
  1. Keep `MODELO_303` mappings coarse and explicit.
  1. Ensure every profile carries citations and source caveats where needed.
- `phase-1-loader`
  1. Add `_corpus.py` with `load_category_profiles_from_manual(year: int)`.
  1. Attempt to read the manual corpus through `aeat.domain.manuals`.
  1. Fall back deterministically to `CATEGORY_PROFILES_2025`.
- `phase-1-cli`
  1. Add `src/aeat/entrypoints/cli/categories.py`.
  1. Mount the subgroup from `src/aeat/entrypoints/cli/__init__.py`.
  1. Keep the commands read-only and explainable.
- `phase-1-tests`
  1. Add `test_spending_category.py`.
  1. Add `test_profile.py`.
  1. Add `test_proportionality.py`.
  1. Add `test_registry.py`.
  1. Add CLI tests so the new commands are covered through Typer.
- `phase-1-verification`
  1. Run `just lint`.
  1. Run `just typecheck`.
  1. Run `just test`.
  1. Run `just hooks`.
  1. Fix root causes only.
- `phase-1-audit`
  1. Write exec records under
     `.vault/exec/2026-04-13-p2e-tax-category-catalogue/`.
  1. Run the mandatory `vaultspec-code-review` pass.
  1. Address findings before finalizing the summary.

## Parallelization

The model and registry work is mostly sequential because the public API depends
on the category enum, proportionality kinds, and casilla mapping shape.

The CLI and tests can fan out once the public model surface is stable. The
corpus loader can land after the registry shape is fixed.

## Verification

- `aeat.domain.financial.categories` exports the full public API.
- Every `SpendingCategory` value has a `CategoryProfile`.
- Every `ProportionalityRule` has at least one citation.
- Every referenced casilla code exists in the current `aeat.domain.casillas` corpus.
- `MODELO_303` mappings remain coarse and honest.
- `just lint && just typecheck && just test && just hooks` is green on Windows.

## Plan review

Reviewer: self.

Outcome: approved.

Checks:

- Scope stays inside TDP step `T4` and does not leak into `#78`, `#79`, `#85`,
  or `#87`.
- `aeat.domain.financial.categories` is the only public feature surface.
- Every boundary model remains strict pydantic v2.
- Every profile remains explainable because citations are mandatory.
- The current-main `303` mapping stays coarse on purpose.
- The user already authorized the full end-to-end vaultspec pipeline with no
  human pause, so this plan is approved for execution.
