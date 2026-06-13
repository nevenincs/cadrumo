---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-wave1-step2-exec]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry-wave1-step2` Code Review


CTR-W1S2-001 | HIGH | Manual corpus schema was rewritten, not just sample text cleaned up

`src/aeat/domain/manuals/_schema.py` now changes persisted/manual boundary behavior: `RuleKind` is no longer the previous enum, translatable `Manual`, `Chapter`, `Section`, and `Rule.statement` fields are now plain strings, `_LegalActRef` requires a pipe-delimited shape, `ManualCatalogue` is now frozen, and `SectionRef.relative_path`/`FetchedManualPart.relative_pdf_path` no longer carry their local path validators. These are real schema and safety changes, not Modelo 130 sample cleanup. In particular, the deleted path validators matter because the manual loader and fetch verification rely on these persisted fields being contained relative paths. This violates the bounded-step claim that only documentation/default suggestions and unused imports changed.

CTR-W1S2-002 | HIGH | Declaración parser public contract changed in a docs-only step

`src/aeat/adapters/inbound/declaracion/_schema.py` removes `ExtractionStatus`, renames the top-level parsed type from `DeclaracionFiling` to `DeclaracionObservation`, and removes the `extraction_status` field from the parsed aggregate. That changes import compatibility and downstream coverage semantics for declaration parsing. Even if later code in the dirty worktree has been adjusted, this is outside the stated shared runtime/docstring/default-suggestion cleanup and can break callers/tests expecting the previous parser contract.

CTR-W1S2-003 | HIGH | Justificante annual-period fallback changed from canonical annual token to observed year

`src/aeat/adapters/inbound/justificante/_extract.py` removed the annual-modelo fallback table and now sets `period = ejercicio` when no explicit period token is found. Previously annual modelos without a period label were normalized to the canonical `0A` token. The updated tests expect `2024`/`2023`, confirming this is an intentional behavior change in the current diff rather than comment cleanup. That can break import, filing-history, or reconciliation paths that match annual filings by `0A`.

CTR-W1S2-004 | HIGH | Export/verify now implements registry export rendering in a cleanup step

`src/aeat/application/filing/_export.py` changed from fail-fast stubs to a full export and verification implementation: it loads the runtime schema provider, renders layouts, writes bytes, parses exported payloads, and emits verification verdicts. This may be valid work for another execution step, but it is a substantial behavior change in a step whose execution note says no registry schema, calculation authority, parser behavior, fixture value, or compatibility path was added. It should be reviewed under the export/filing-linkage step, not hidden inside generic Modelo 130 sample cleanup.

CTR-W1S2-005 | MEDIUM | Application error registry now references missing translation keys and non-copyable placeholder suggestions

`src/aeat/core/errors/registry/_application.py` replaces inline default messages with `message_key` values such as `errors.error.error_financial_aggregation` and `errors.refused.refused_financial_aggregation_unsupported_modelo`, but the locale files do not contain those keys. `get_error_message` resolves message keys through the CLI i18n backend, so missing keys risk surfacing raw keys instead of user-facing messages. The replacement suggestions `aeat app declaration calculate --modelo MODELO --period PERIOD` also remove the Modelo 130 sample but are still presented as copy-paste recovery commands while containing bare placeholders. Prefer a non-model-specific but executable/obviously templated string, such as using angle-bracket placeholders if the UX contract allows them, and add locale coverage for the new keys.

CTR-W1S2-006 | MEDIUM | Filing profile protocol lost an application-facing property

`src/aeat/domain/filing/_protocols.py` removes `FilingProfile.applicable_modelos`. Even if current filing code no longer reads it, deleting a protocol member changes the public typing contract for richer profile objects. That is outside the bounded docs/default-suggestion scope and should be tied to the registry-backed applicability migration if it is intentional.

## Checks

- Scoped search found no remaining generic Modelo 130 sample references in the listed runtime files after the cleanup.
- Scoped search did not show legally meaningful Modelo 130 registry/corpus/fixture authority removal in the reviewed bounded surface.
- I did not review or modify Modelo 111 behavior.
- I did not run the full test suite; findings above are based on the scoped diff, code search, and line-level inspection.

## Residual Risk

The worktree is heavily dirty beyond this bounded step, so some behavior changes may belong to adjacent execution steps. They still appear inside the user-provided review scope and should not be accepted as part of a docs/default-suggestion-only teardown step without separate review.
