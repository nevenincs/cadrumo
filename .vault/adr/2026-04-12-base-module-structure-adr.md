---
tags:
  - "#adr"
  - "#base-module-structure"
date: 2026-04-12
modified: '2026-04-12'
superseded_by: "[[2026-04-30-aeat-restructure-adr]]"
related:
  - "[[2026-04-12-base-module-structure-research]]"
  - "[[2026-04-30-aeat-restructure-adr]]"
---
# Base Module Structure ADR
Date: 2026-04-12

## Context
Multiple parallel streams of work are planned for `aeat` automation. Without a unified, pre-locked base structure, each feature branch will create its own inconsistent subpackage styling, test conventions, and API exposure.

## Decisions
1. **Package Layout**: Establish typed, empty subpackages under `src/aeat/`: `models`, `portals`, `auth`, `schema`, `storage`, `sync`, `browser`, `corpus`, and `cli`.
2. **Public API Discipline**: Every subpackage MUST expose its public API exclusively through its `__init__.py`. External code within the project must only import from the package root (e.g. `from aeat.domain.modelos import ModelCatalogue`).
3. **Type Style**:
   - `enum.Enum` for closed catalogues (e.g., portals, models).
   - `dataclass` for internal value objects.
   - `pydantic` models for validated wire and configuration data.
4. **CLI Framework**: We adopt `typer` since it is modern, type-hint native, integrates natively with `pydantic` workflows, and is already in the project's dependency tree.
5. **Logging Framework**: We will use standard library `logging` configured via `dictConfig` to provide a consistent project logger factory (`aeat.core.logging.get_logger`). This minimizes third-party dependency bloat while still enforcing centralized formatting.
6. **Errors**: A central `AeatError` base class defined in `src/aeat/errors.py`. All domain-specific errors must inherit from this.
7. **Colocated Testing**: Following Rust-style conventions, each subpackage contains its own tests (e.g., `src/aeat/domain/modelos/test_smoke.py`). Every test explicitly specifies `@pytest.mark.unit` or `@pytest.mark.live`.

## Status
Accepted.
