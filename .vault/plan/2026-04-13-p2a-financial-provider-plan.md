---
tags:
  - "#plan"
  - "#p2a-financial-provider"
date: "2026-04-13"
modified: '2026-04-13'
related:
  - "[[2026-04-13-p2a-financial-provider-research]]"
  - "[[2026-04-13-p2a-financial-provider-adr]]"
---

# `p2a-financial-provider` `phase-1` plan

Deliver the T1 ingest substrate for issue `#73`: strict file-backed `RawTransaction` production from CSV, XLSX, and OFX sources, plus a minimal CLI entry point and the supporting fixtures/tests.

## Proposed Changes

- Create the new `aeat.domain.financial` subpackage and expose the public ingest API exclusively through package roots.
- Define the strict frozen pydantic boundary models for raw transactions, provenance, source format, and provider validation.
- Implement the provider ABC, CSV/XLSX/OFX providers, and provider auto-detection.
- Wire `aeat financial ingest` into the root CLI and extend settings / `.env.example`.
- Add deterministic fixtures and colocated tests for provider behavior, detection, validation, and CLI output.

## Tasks

- `Phase 1: establish the T1 boundary types and provider surface`
  1. Create `aeat.domain.financial` public exports plus `_raw_transaction.py` and provider base models/exceptions.
  1. Add provider detection and root-package exports consistent with the repo's public API discipline.
- `Phase 2: implement file providers`
  1. Implement `CsvProvider` with bank-layout mappings, encoding/dialect detection, and deterministic ID synthesis.
  1. Implement `XlsxProvider` with header-row detection and row normalization through `openpyxl`.
  1. Implement `OfxProvider` with `ofxparse` and deterministic provenance mapping.
- `Phase 3: wire configuration and CLI`
  1. Add the financial settings fields and align `env/.env.example`.
  1. Add the `aeat financial ingest` Typer surface and register it in the root CLI.
- `Phase 4: verify with real fixtures`
  1. Add synthetic fixtures for CSV/XLSX/OFX plus one real-bank-style CSV fixture each for BBVA, Santander, CaixaBank, and Revolut.
  1. Add colocated unit tests for models, providers, detection, settings alignment, and CLI output.
  1. Run `just lint`, `just typecheck`, `just test`, and `just hooks`, then perform the mandatory code review and resolve any high-severity findings.

## Parallelization

The code is coupled enough that the cleanest path is sequential execution: first define the boundary models and shared helpers, then implement providers, then wire CLI/config, then add fixtures/tests, then review. The only safe parallel slice is document drafting versus code discovery, which is already complete.

## Verification

- `RawTransaction` and `RawProvenance` validate strictly, reject extra fields, and preserve immutable provenance data.
- `detect_provider(path)` selects the correct provider for CSV, XLSX, and OFX fixtures.
- CSV ingestion succeeds for BBVA, Santander, CaixaBank, and Revolut real-bank-style fixtures, including semicolon/comma delimiters and non-UTF-8 text where applicable.
- XLSX ingestion succeeds against a real workbook fixture using `openpyxl`.
- OFX ingestion succeeds against a real OFX fixture and honors `FITID` when present.
- `aeat financial ingest <path>` validates first, exits non-zero on invalid sources, and emits JSON lines when `--output-json` is passed.
- `just lint && just typecheck && just test && just hooks` pass on this branch.

## Explicit Plan Review

- **Issue scope check:** The plan stays inside `T1 — Ingest` and does not reach into T2 normalization, T5 persistence, or any `vat/` or `categories/` namespace work.
- **Dependency check:** The plan adds only the missing parser libraries needed for the provider implementations and does not assume sibling-branch types.
- **Convention check:** Public API discipline, strict pydantic boundary models, colocated tests, and root-CLI registration are all covered.
- **Review outcome:** Approved for execution under the user's explicit no-pause instruction.
