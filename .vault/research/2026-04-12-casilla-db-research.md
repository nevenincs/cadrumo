---
tags:
  - "#research"
  - "#casilla-db"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-data-storage-adr]]"
  - "[[2026-04-12-trilingual-i18n-adr]]"
---

# Casilla DB Research

## Context
Issue #23 needs a new curated casilla catalogue that can land without colliding with the in-flight `aeat.domain.schema` work from issue #9. The branch must also respect the already-landed storage, i18n, CLI, and package-layout conventions on `main`.

## Findings

### Package and ownership boundaries
- Issue #23 originally targeted `src/aeat/domain/schema/casillas.py`, but `src/aeat/domain/schema/` is owned by issue #9 and is explicitly in flight.
- The current repository already accepts additive subpackages that were not in the original issue #12 list (`aeat.adapters.outbound.aeat.browser`, `aeat.core.i18n`, `aeat.corpus`), so a new `src/aeat/domain/casillas/` package is the lowest-conflict option.
- Public API discipline on this branch is enforced through typed `__init__.py` exports and smoke tests that assert `__all__` completeness.

### Existing implementation conventions
- Boundary-crossing records in the codebase use pydantic v2 models with `ConfigDict(strict=True, frozen=True)` where immutability is reasonable.
- Domain errors inherit from `aeat.core.errors.AeatError`.
- Logging uses `aeat.core.logging.get_logger(__name__)`.
- Typer command groups are mounted from `src/aeat/entrypoints/cli/__init__.py`.
- Live tests are opt-in through `AEAT_LIVE_TESTS_ENABLED` and helper gates in `src/aeat/entrypoints/cli/_live.py`.

### Dependency coordination
- `aeat.domain.modelos`, `aeat.domain.schema`, `aeat.adapters.outbound.llm`, `aeat.domain.manuals`, and `aeat.corpus` all have in-flight owners or not-yet-landed surfaces.
- The safest integration strategy on this branch is to define Protocol-based stubs for:
  - `Casilla`, `FormulaNode`, `ValidationRule` from issue #9
  - `LLMClient` and bulk translation surface from issue #21
  - `Rule` references from issue #25
- The persisted casilla records should use stable string identifiers (`MODELO_130`, etc.) validated against a small known set until issue #6 lands.

### Storage shape and verification
- The repository already standardized on diff-friendly git-tracked JSON for corpus-style artefacts and SQLite/SQLAlchemy for operational state.
- Issue #23 is better served by JSON corpus files than by the SQL storage layer because:
  - hand review is central to the workflow,
  - the data should diff cleanly in git,
  - the acceptance criteria explicitly call for `corpus/casillas/<modelo>/<period>.json`.
- Verification needs two layers:
  - pydantic parsing for each record and catalogue,
  - structural validation for duplicate keys, dangling same-period casilla references, missing reviewer metadata, and missing authoritative Spanish translations.

### Current authoritative sources and period choice
- AEAT currently exposes a live HTML manual for VAT 2025 and a PDF for the same manual on the official `sede.agenciatributaria.gob.es` domain.
- The `modelo 303` instructions page is published for exercise 2025.
- The `modelo 130` instructions page is currently served from the official AEAT site as a stable HTML page without a year in the path.
- The `modelo 390` instructions for exercise 2025 are published as an official AEAT PDF.
- Given the current date of 2026-04-12, the most recent fully completed filing periods are:
  - `MODELO_130`: `2025Q4`
  - `MODELO_303`: `2025Q4`
  - `MODELO_390`: `2025`
- This period selection is an inference from the calendar and should be called out explicitly in the ADR.

### LLM-as-draft-only workflow
- The branch cannot hard-import `aeat.adapters.outbound.llm` yet, but the CLI can still define draft-oriented workflows behind Protocols so the call sites stabilize now and rebind cleanly once issue #21 lands.
- `extract` and `translate` should write draft JSON to a temporary file outside `corpus/casillas/` and should not mutate the canonical corpus in place.
- `verify` must reject canonical records that lack `reviewed_by` and `reviewed_at`.

### Documentation implications
- The repo-level instructions require a structured documentation workflow for user-facing docs.
- The most practical documentation deliverable for this issue is a reference-style contributor document that explains:
  - how to add a new modelo+period file,
  - how to use the draft extraction and translation commands,
  - how to review and verify a casilla corpus file before commit.

## Recommendation
- Create a new `aeat.domain.casillas` subpackage with strict pydantic models, Protocol stubs for upstream dependencies, JSON loader/saver/verification helpers, and Typer subcommands mounted at `aeat casillas`.
- Store canonical files under `corpus/casillas/<modelo>/<period>.json`.
- Validate three initial catalogues for `MODELO_130`, `MODELO_303`, and `MODELO_390` using 2025-complete periods.
- Enforce the draft-only workflow in code by making `extract`/`translate` output temp files and `verify` reject unreviewed canonical records.
