---
tags:
  - "#reference"
  - "#base-module-structure"
date: 2026-04-12
modified: '2026-04-12'
superseded_by: "[[2026-04-30-aeat-restructure-adr]]"
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
---
# AEAT Base Module Structure Conventions
Date: 2026-04-12

These conventions apply to all modules under `src/aeat/`.

## 1. Package Layout
All Python code must live under `src/aeat/`. No top-level scripts, no `lib/`, no ad-hoc directories.

## 2. Public API Discipline
Code outside a subpackage MUST only import from the subpackage's `__init__.py`.
- **Valid:** `from aeat.domain.modelos import ModelCatalogue`
- **Invalid:** `from aeat.domain.modelos.catalogue import ModelCatalogue`

## 3. Type Style
- **Enums:** Use for closed catalogues (e.g., models, portals).
- **Pydantic Models:** Use for validated wire or config data.
- **Dataclasses:** Use for internal value objects.
Do not use bare dictionaries in public signatures.

## 4. Docstrings
Google-style docstrings and full type hints are required on all public symbols.

## 5. Testing
Tests are colocated with the code they test (Rust style). For example, `src/aeat/domain/modelos/test_smoke.py`.
Every test must be marked with either `@pytest.mark.unit` or `@pytest.mark.live`.
Live tests must NEVER use mocks, patches, fakes, or stubs.

## 6. Errors
All domain errors must inherit from `aeat.core.errors.AeatError`. Do not raise raw `Exception` in feature code.

## 7. Logging
Use the `aeat.core.logging.get_logger(__name__)` factory. Do not scatter `logging.getLogger` calls without going through the project factory.
