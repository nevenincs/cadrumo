---
tags:
  - '#adr'
  - '#code-duplication-sweep'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-05-19-code-duplication-sweep-research]]'
  - '[[2026-05-19-spanish-stem-terminology-authority-adr]]'
status: superseded
---

> **SUPERSEDED 2026-05-19**: This ADR is superseded by the Spanish-stem
> terminology authority ADR (see related link above). Specifically, the
> W03.P04 VAT-wins direction is REVERSED: Spanish stems are authoritative
> for tax-domain identifiers, `IvaInvoiceClassification` is canonical, and
> `domain/vat` migrates into `domain/iva`. All other structural decisions
> in this ADR (W01 minor symbol segregations, W02 boilerplate
> consolidation, W03.P05 borrador deduplication) remain in force where
> the existing plan executes against them.

# `code-duplication-sweep` adr: `Unify Shadowed Symbols, Secure Object Repositories, and Terminology Glossary` | (**status:** `superseded`)

## Problem Statement

During a deep structural audit of the codebase, we identified several patterns of code duplication, symbol shadowing, and terminology drift that threaten long-term maintenance:
- **Shadowed Exceptions and Imports**: `WorkUnitNotFoundError` is defined independently in both `_actions.py` and `_reconcile.py`, which risks import shadow bugs. The `CCAA` enum in `_festivos.py` collides with the profile-scoped `CCAA` enum, and the metadata facade `ModeloRepository` in `modelos.py` shadows the actual persistent repository.
- **Copy-Pasted Storage Boilerplate**: Multiple pydantic/secure object repositories (such as `FilingDraftRepository`, `SubmissionRepository`, and `FilingHistoryRepository`) duplicate similar file pathing, locking, and serialization logic.
- **Parser and Integration Redundancies**: Parallel pdfplumber text extraction code is scattered across different inbound parser backends, and live oracle replay drivers repeat JSON-decoding operations.
- **Acronym and Caching Drift**: Divergent terminology exists for Value-Added Tax (`VAT` vs `IVA`), and an insecure local file-caching strategy in `_borrador.py` bypasses secure storage boundaries.

## Considerations

- Maintain strict separation of domain logic and infrastructure adapters as mandated by hexagonal architectural boundaries.
- Adhere to the zero-mock policy by using real SQLite, SQLiteEncrypted, and KeyProvider adapters in all roundtrip tests.
- Ground tax calculations in authoritative legal/regulatory references.
- Simplify developer onboarding by reducing cognitive load and preventing future structural divergence.

## Constraints

- Refactoring must not break external CLI interface expectations or core database roundtrip integrity.
- All refactoring steps must maintain strict compatibility with the existing Pydantic v2 schemas and model validation mechanisms.
- All tests must pass cleanly under modern PowerShell in a Windows 11 environment.

## Implementation

- **Unify Shadowed Symbols**: Consolidate `WorkUnitNotFoundError` into the canonical `_actions.py` module and import it where needed. Rename the calendar-specific `CCAA` enum to `CalendarCCAA`, and rename the static metadata helper `ModeloRepository` to `StaticModeloRepository`.
- **Generic Bound Persistence**: Introduce a base `SecureBoundRepository[T]` generic class in `_secure_repository.py` that encapsulates common file path, locking, and roundtrip serialization, and refactor existing repositories to inherit from it.
- **Unify Integrations**: Move pdfplumber extraction to `_pdfplumber.py` and have all parsers use it. Extract a common `BaseCheckerOracle` for live checkers to share JSON-decoding and replay logic.
- **Acronym & Caching Standardisation**: ~~Build a unified `VatClassification` domain model under `domain/vat`~~ **[SUPERSEDED â€” see superseding ADR; the direction is reversed. Consolidate into `IvaInvoiceClassification` under `domain/iva` instead.]** Deprecate the insecure local file-caching in `_borrador.py` in favor of the secure `_borrador_100.py` object repository, and update terminology across the codebase per the superseding ADR canonical rename ledger.

## Rationale

Unifying shadowed symbols prevents runtime import collision and catching bugs. Consolidating secure storage logic under `SecureBoundRepository[T]` simplifies persistence adapters, enforces secure locking consistently, and reduces the testing surface. Shared PDF extraction and base oracle drivers eliminate boilerplate and make external integrations easy to maintain.

## Consequences

- Introducing `SecureBoundRepository[T]` will simplify persistence maintenance but requires refactoring several repository test suites.
- Deprecating local caching in `_borrador.py` requires updating test fixtures to rely on secure-bucket storage, ensuring higher security.
- Standardizing terminology reduces confusion around tax semantics â€” see superseding ADR for the canonical rename ledger.
