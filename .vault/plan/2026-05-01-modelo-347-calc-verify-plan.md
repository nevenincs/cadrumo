---
tags:
  - '#plan'
  - '#modelo-347-calc-verify'
date: '2026-05-01'
related:
  - '[[2026-05-01-modelo-347-calc-verify-research]]'
  - '[[2026-05-01-modelo-347-calc-verify-adr]]'
---

# `modelo-347-calc-verify` `implementation` plan

Ship Tier-S Modelo 347 import verification for exercises 2024, 2025, and 2026 by extracting typed per-counterparty records and verifying resumen totals parity.

## Proposed Changes

Add a strict M347 domain record model and per-year manifests, extend the declaracion extractor from summary-only to summary-plus-detail records, add a summary verifier that returns the existing Kent-facing verdict type, wire the CLI to that verifier, and add synthetic-PDF round-trip plus CLI smoke coverage.

## Tasks

- Phase 1 - Domain records and manifests
  1. Add `domain/modelos/m347` strict records and enums.
  1. Add `_rules_2024`, `_rules_2025`, and `_rules_2026` manifests.
  1. Add unit coverage for validation and manifest identity.
- Phase 2 - Extractor extension
  1. Add `modelo_347_records` to the declaration boundary record.
  1. Override the M347 extractor to parse detail rows and register 2024 / 2026 siblings.
  1. Add round-trip extractor tests using real generated PDFs.
- Phase 3 - Summary verifier and CLI
  1. Add the Tier-S parity verifier.
  1. Wire `aeat filing import --from-declaracion` for M347.
  1. Add CLI smoke tests for verified and mismatch paths.
- Phase 4 - Coverage docs and exec records
  1. Update coverage matrices for M347 2024 / 2025 / 2026.
  1. Persist execution summary and code review artifacts.
  1. Run targeted tests, import-linter, and coverage.

## Parallelization

The work is mostly sequential because the extractor and verifier depend on the domain record shape. Documentation and final review can run after tests are green.

## Verification

Success means the M347 extractor produces strict detail records for all three supported years, the generated PDF round-trip preserves every field, the summary verifier emits `VERIFIED` on parity and `NEEDS_REVIEW` on count or amount drift, the CLI smoke test exercises the full import path, and `just lint-imports` plus targeted tests remain green.
