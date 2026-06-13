---
tags:
  - "#adr"
  - "#n26-data-source"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-14-n26-data-source-research]]"
  - "[[2026-04-14-n26-data-source-adr]]"
  - "[[2026-04-13-p2a-financial-provider-adr]]"
  - "[[2026-04-21-n26-data-source-audit]]"
---

# `n26-data-source` adr: `fixture-backed-live-pdf-provider` | (**status:** `accepted`)

## Problem Statement

Issue `#308` is the actual implementation vehicle for the N26 statement feature. The merged research under `#106` established that monthly PDF statements are the right T1 ingest channel, but it did not decide how to source real statements, sanitize them into committed fixtures, ground manual golden expectations, or fit the provider into the code that now exists on `main`. We need an implementation decision that turns the research conclusion into a concrete, reviewable feature without inventing a parallel ingest/storage architecture.

## Considerations

- The live codebase already exposes the T1 boundary through `FinancialProvider`, `RawTransaction`, `RawProvenance`, `detect_provider()`, and `aeat financial ingest`. Today that surface only covers CSV, XLSX, and OFX.
- `pdfplumber` is already a pinned project dependency and is already used elsewhere in the repo for real PDF parsing. N26 PDF work does not need a new parser stack, OCR layer, or ML dependency.
- The current provider substrate persists provenance as `source_path`, `source_sha256`, and `source_row_index`, but it does not expose a raw-document archive setting such as the research-era `AEAT_FINANCIAL_RAW_DIR` sketch. The implementation decision must align with the real codebase, not the research sketch.
- The repo already has patterns for committed synthetic/sanitized PDF fixtures and for parser tests that use real file I/O with no mocks or patches.
- The user requirement is stronger than "parser works on one fake PDF". The feature is not done until it is grounded in at least one real N26 statement template, sanitized into committed fixtures, and verified against hand-derived transaction expectations.
- The current CLI ingest path is still read-only. `#216` remains the open T1→T2 persistence bridge and must be treated as adjacent scope rather than silently assumed to exist.

## Constraints

- No real financial data, identifiers, or raw unsanitized statements may be committed to the repository.
- The fixture corpus must remain PDF-backed. If direct redaction damages parser fidelity, the committed fixture may be a layout-faithful reconstructed PDF derived from the real statement, but the reconstruction must still be grounded in a real N26 template.
- Golden expectations must be derived by manually reading the fixture and transcribing the expected rows, amounts, dates, currencies, balances, and continuation semantics. Parser output cannot be used to generate its own oracle.
- The implementation should stay inside `aeat.domain.financial` and `aeat.domain.financial.providers`, plus the minimal CLI/provider-selection changes needed for ingest. It must not introduce a new parallel raw-document storage subsystem in this issue.
- Tests must use real file behavior and useful assertions. No mocks, patches, stubs, `skip`, or tautological self-checks.

## Implementation

- **Fixture-first execution.** The first deliverable is a committed N26 fixture corpus under `tests/fixtures/financial/n26/`, sourced from one or more real statements and sanitized before commit. Each fixture gets a manually prepared golden expectation artifact and a short operator note describing what was preserved, replaced, and reconstructed.
- **Provider shape.** Add `SourceFormat.PDF` to `RawProvenance`, implement `PdfN26Provider` under `aeat.domain.financial.providers`, and register it in the provider exports, auto-detection, and CLI provider selection.
- **Parser approach.** Use `pdfplumber` on vector text only. Detect locale and statement headers from page text, derive table bands from the statement's own header words instead of fixed coordinates, parse dates locale-safely, and extract the statement currency from the document rather than hard-coding `"EUR"`.
- **Row model mapping.** Emit one `RawTransaction` per visual transaction row in reading order across page breaks. Use the statement row ordinal as `source_row_index`. Preserve the verbatim cell text and any continuation payloads in `raw_fields`, including FX and SEPA continuation lines when present. The canonical `amount` remains the booked amount shown by the statement; continuation details stay in provenance payloads for later pipeline stages.
- **Sanitization architecture.** Prefer direct PDF redaction/replacement when it preserves geometry. If that breaks table extraction or text ordering, generate a layout-faithful synthetic PDF from manually extracted statement structure and use that reconstructed artifact as the committed fixture. The committed test surface is therefore "sanitized-or-reconstructed but layout-valid", never raw.
- **Scope boundary.** This issue ships the live PDF read path, auto-detection, CLI ingest support, fixtures, tests, review, and audit loops. It does not introduce a new raw-PDF archive directory or absorb the broader ingest-persistence bridge from `#216` unless a trivial integration becomes necessary during implementation.
- **Explicit deferral.** The earlier research sketch's N26 CSV extension remains deferred until the PDF path is complete and audited. The user asked for the live PDF statement pipeline specifically; that is the execution priority.

## Rationale

- A fixture-first ADR prevents the common failure mode where parser code lands against invented PDFs and later collapses on real statements.
- Reusing `pdfplumber` keeps the implementation aligned with the repo's existing PDF parsing stack and avoids duplicate parser abstractions.
- Rejecting a new raw-document archive surface in this issue avoids shadowing the existing attachment/storage work and keeps the N26 feature anchored to the substrate that actually exists on `main`.
- Storing continuation semantics inside `raw_fields` matches the current `RawTransaction` contract. It preserves inspector-grade provenance without prematurely widening the T1 boundary just for one bank.
- Deferring CSV and persistence expansion keeps the issue coherent: the user asked to finish the PDF statement reading pipeline, not to reopen every adjacent financial-ingest issue at once.

## Consequences

- This feature is now blocked on obtaining and sanitizing at least one real N26 statement template. Research is complete; fixture acquisition is the first execution task.
- The implementation ADR supersedes the research ADR's archive-setting sketch. Provenance remains complete through `source_path`, `source_sha256`, `source_row_index`, and verbatim `raw_fields`, but raw-document mirroring is not part of this issue.
- The final provider will make `aeat financial ingest <statement.pdf>` work for N26 PDFs, but one-command persistence into the transaction catalogue still belongs to `#216` unless we discover a tiny safe integration during execution.
- Review and audit are part of the feature definition, not postscript work. The feature is unfinished until manual fixture reading, pytest coverage, and code-review findings are exhausted.

## Explicit ADR Review

- **Codebase alignment:** accepted. The ADR names only live modules and gaps that exist on `main`: `SourceFormat`, the provider registry, auto-detection, and the ingest CLI.
- **Research alignment:** accepted. The research decision to prefer PDF statements remains unchanged; only the implementation mechanics have been tightened to match the real repo.
- **Scope alignment:** accepted with one narrowing change. N26 CSV extension and raw-document archiving are deferred so the live PDF provider can be implemented without shadowing adjacent work.
