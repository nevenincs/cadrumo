---
tags:
  - '#adr'
  - '#modelo-347-calc-verify'
date: '2026-05-01'
related:
  - '[[2026-05-01-modelo-347-calc-verify-research]]'
  - '[[2026-04-21-calc-verification-adr]]'
  - '[[2026-04-21-declaracion-extractor-adr]]'
---

# `modelo-347-calc-verify` adr: `typed detail records plus resumen parity` | (**status:** `accepted`)

## Problem Statement

Kent must be able to import a Modelo 347 declaracion PDF for 2024, 2025, or 2026 and receive a real verification verdict. Modelo 347 has no computed casillas, so the existing formula-ruleset verifier cannot be the authority. The authority is detail-to-summary parity.

## Considerations

The post-restructure architecture places Modelo catalogue and typed domain records under `domain/modelos`, PDF extraction under `adapters/inbound/declaracion`, and verification orchestration under `application/verification`. The import-linter contract allows inbound adapters and application services to depend on domain records, but domain code must not import adapters.

Orden EHA/3012/2008 defines the type-2 declared-person record fields and the summary total relationship. The current M347 extractor has only a four-casilla summary MVP. The existing `VerificationVerdict` is reusable for Kent-facing status and trilingual narrative.

## Constraints

No live AEAT submit path can be added. No formula ruleset should be registered. Boundary records must be pydantic v2 frozen, strict, and extra-forbid. User-facing strings must use the trilingual `Translatable` shape. Tests use real generated PDFs and real parser/verifier execution.

## Implementation

Create `Modelo347RecordLine` in `domain/modelos/m347` with strict Decimal monetary fields, date/enum closed catalogues where applicable, and validators for two-cent decimal precision and annual-vs-quarterly consistency. Add year manifests for 2024, 2025, and 2026 that encode threshold, summary casillas, supported fields, and operation-key catalogue.

Extend `DeclaracionFiling` with a default-empty `modelo_347_records` tuple. Override the M347 extractor to call the existing generic summary-casilla path and then parse deterministic detail lines into `Modelo347RecordLine` instances. Add thin 2024 and 2026 extractor subclasses and register all three years.

Add `_verify_summary.py` in `application/verification`. It returns `VerificationVerdict` for M347 by checking count and amount parity within `0.01`. The CLI dispatches to this verifier when `filing.modelo == "347"` before falling back to formula-ruleset resolution.

## Rationale

A sibling summary verifier preserves the formula verifier's contract and makes the Tier-S rule visible. Encoding year manifests under `domain/modelos/m347` avoids pretending M347 has formulas while still representing schema drift explicitly. The detail-record tuple on `DeclaracionFiling` is narrow and default-empty, so existing modelos do not change behavior.

## Consequences

Kent receives `VERIFIED` for clean M347 PDFs and `NEEDS_REVIEW` with concrete deltas when the printed resumen disagrees with the detail rows. Future M347 schema changes can land as manifest deltas and extractor updates without altering the CLI contract.
