---
tags:
  - "#plan"
  - "#n26-data-source"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-14-n26-data-source-research]]"
  - "[[2026-04-14-n26-data-source-adr]]"
  - "[[2026-04-21-n26-data-source-implementation-adr]]"
  - "[[2026-04-13-p2a-financial-provider-adr]]"
---

# `n26-data-source` `phase-2` plan

Execute the real N26 PDF statement feature as issue `#308`: source a real statement template, sanitize or reconstruct committed PDF fixtures, implement the `PdfN26Provider`, wire it into CLI auto-detection, and keep iterating through review and audit loops until no live/manual/pytest-discovered defects remain.

## Proposed Changes

- Build a committed N26 fixture corpus grounded in real statements rather than invented examples. Each fixture must preserve parser-relevant layout and come with manually transcribed golden expectations.
- Extend the T1 ingest substrate with `SourceFormat.PDF` and a concrete `PdfN26Provider` that emits strict `RawTransaction` records with complete provenance and verbatim `raw_fields`.
- Extend provider auto-detection and the `aeat financial ingest` CLI so N26 statements work through both `--provider auto` and an explicit provider selection when useful.
- Add fixture-backed tests for locale handling, multi-page tables, continuation rows, sanitization/reconstruction fidelity, and end-to-end CLI ingest behavior.
- Run formal review plus repeated audit loops over the feature until the remaining failures are exhausted, documenting any truly out-of-scope residual risk honestly.

## Tasks

- `Phase 1: source and ground the fixture corpus`
  1. Locate or obtain at least one real, valid N26 monthly statement template from the operator environment and inspect its page structure manually.
  1. Build a repeatable sanitization flow that preserves parser geometry; if direct redaction breaks the layout, reconstruct a layout-faithful synthetic PDF from the real statement structure.
  1. Commit the resulting fixture PDFs under `tests/fixtures/financial/n26/`.
  1. Hand-read every committed fixture and record the expected rows, dates, amounts, currencies, balances, and continuation semantics in golden expectation files.
- `Phase 2: implement the provider surface`
  1. Add `SourceFormat.PDF` in `aeat.domain.financial._raw_transaction`.
  1. Implement `PdfN26Provider` with header-derived table geometry, locale-aware date parsing, statement-derived currency, and continuation-row handling.
  1. Register the provider in `aeat.domain.financial.providers`, extend `detect_provider()`, and update `aeat financial ingest` provider resolution.
- `Phase 3: prove behavior with fixture-backed tests`
  1. Add unit tests that ingest the committed fixtures and compare emitted `RawTransaction` records against the hand-derived goldens.
  1. Add CLI coverage proving `aeat financial ingest <fixture.pdf>` succeeds under auto-detection and surfaces clear validation failures for non-N26 PDFs.
  1. Add explicit regression coverage for multi-page row ordering, locale shifts, FX continuation rows, and sanitization/reconstruction edge cases.
- `Phase 4: review and exhaust the audit loop`
  1. Run lint, typecheck, and focused pytest for the touched financial/provider/CLI surfaces.
  1. Perform formal code review of the implementation and fix every critical/high finding.
  1. Run manual fixture walkthroughs against the committed PDFs and reconcile any mismatch between human reading and parser output.
  1. Re-run targeted tests after each fix until live/manual/pytest-discovered problems are exhausted.
- `Phase 5: close adjacent scope honestly`
  1. Re-check the T1→T2 persistence gap against `#216` after the provider lands.
  1. If a minimal safe integration is obvious, land it; otherwise record the exact remaining boundary instead of pretending the pipeline is fully persisted.

## Execution Status

- Phase 1 is partially complete. No local operator PDF was recoverable, but a public sanitized corpus grounded in real N26 savings-account statements was recovered and used to build committed deterministic PDF fixtures plus hand-maintained expected ledgers.
- Phase 2 is complete for the recovered template family. `SourceFormat.PDF`, `PdfN26Provider`, provider exports, auto-detection, and CLI ingest support are all implemented.
- Phase 3 is complete for the committed savings fixtures. Provider and CLI tests compare parser output against manually maintained expected rows.
- Phase 4 is partially complete. Targeted lint, typecheck, pytest, and manual CLI inspection are green, but the audit still records one medium residual gap: fixture breadth has not yet reached the broader current-account / FX statement family from the original research.
- Phase 5 remains open. The provider read path is real and working, but the T1→T2 persistence bridge remains an adjacent issue (`#216`) unless folded in later.

## Parallelization

The critical path is mostly sequential. Fixture sourcing and manual golden transcription must happen before the parser can be trusted, and the provider must exist before review and audit loops become meaningful. The only safe overlap is small-scale: sanitization tooling can evolve while provider scaffolding is written, and CLI wiring can proceed while fixture goldens are being finalized.

## Verification

- A committed N26 PDF fixture corpus exists and is visibly grounded in a real statement template rather than an invented document.
- Every fixture has manually derived expected transactions and those expectations are stored separately from parser code.
- `PdfN26Provider` emits correct `RawTransaction` rows for simple, multi-page, locale-shift, and continuation-heavy statements.
- `detect_provider()` recognizes N26 PDFs without breaking existing CSV/XLSX/OFX detection.
- `aeat financial ingest <fixture.pdf>` works end-to-end on the N26 fixtures.
- Lint, typecheck, and the targeted pytest surface for financial providers and CLI pass.
- Manual fixture review and formal code review produce no unresolved critical/high findings.
- If persistence into the catalogue still remains outside this issue, the final state says so explicitly and points at `#216` with no ambiguity.

## Explicit Plan Review

- **Issue scope check:** the plan matches the user's reframing of `#308` as the actual execution vehicle for the live PDF statement feature.
- **ADR check:** the plan follows the implementation ADR's narrowing decisions: PDF first, no parallel raw-archive subsystem, no parser-oracle goldens, and no fake fixtures.
- **Codebase check:** the plan targets only code seams that exist today on `main`: `SourceFormat`, provider registration, provider detection, and the financial ingest CLI.
- **Audit honesty check:** the plan requires manual statement reading and repeated audit loops, so "tests pass" alone is not enough to declare the feature done.
