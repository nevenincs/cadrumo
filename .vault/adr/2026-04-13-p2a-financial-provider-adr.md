---
tags:
  - "#adr"
  - "#p2a-financial-provider"
date: "2026-04-13"
modified: '2026-04-13'
related:
  - "[[2026-04-13-p2a-financial-provider-research]]"
  - "[[2026-04-12-base-module-structure-adr]]"
---

# `p2a-financial-provider` adr: `file-first-t1-ingest-surface` | (**status:** `accepted`)

## Problem Statement

Issue `#73` must establish the T1 ingest boundary for the entire financial pipeline: a provider ABC plus CSV, XLSX, and OFX implementations that emit strict `RawTransaction` records with enough provenance to answer exactly where each record came from.

## Considerations

- The implementation must conform to current repo conventions instead of the older issue body, which still refers to `src/aeat/domain/financial/sources/` and an async fetch surface.
- `#74` is not on `main`, so this issue cannot depend on a sibling transaction catalogue type.
- Spanish bank CSV exports are layout-variant but structurally similar; Revolut is structurally distinct and should still be supported by the same CSV provider through bank-specific column maps.
- Validation must be explicit and user-visible because file ingest errors are common: wrong encoding, wrong delimiter, wrong worksheet, wrong extension, or non-bank CSVs.

## Constraints

- Public API must be exposed from `aeat.domain.financial` and `aeat.domain.financial.providers` only.
- Boundary-crossing types must be strict frozen pydantic v2 models with `enum.StrEnum` closed sets and no bare `dict[...]` signatures.
- T1 ingest stays file-based only. No persistence, normalization, FX conversion, VAT logic, or Google Workspace behavior belongs in this issue.

## Implementation

- Create `src/aeat/domain/financial/` with a public `__init__.py`, a concrete `_raw_transaction.py`, and a `providers/` package containing the ABC, concrete providers, and provider auto-detection.
- Use a strict frozen `RawTransaction` model with a nested strict frozen `RawProvenance` model containing `source_path`, `source_sha256`, `source_row_index`, `source_format`, `ingested_at`, and `provider_name`.
- Adopt a strict frozen `ProviderValidation` model as the validation contract returned by every provider.
- Implement CSV ingestion through a configurable set of bank layouts expressed as pydantic models that define header aliases and date/number parsing strategies.
- Implement XLSX ingestion through `openpyxl` in read-only/data-only mode with header-row detection over the first several rows.
- Implement OFX ingestion through `ofxparse`, preferring `FITID` as the stable provider ID and falling back to a deterministic synthetic ID when necessary.
- Add a new Typer sub-app `aeat financial` with `ingest` as the initial command surface and wire it into the root CLI.

## Rationale

- A concrete `RawTransaction` in T1 is the cleanest upstream contract. It lets `#74` extend or wrap the ingest record later without blocking the file providers today.
- A synchronous ABC matches the current scope better than the older async issue body because file ingest is local, bounded, and not I/O multiplexing heavy.
- Putting all four bank CSV layouts behind a single provider avoids premature fragmentation while still keeping the parsing logic explicit and testable.
- Extension-first detection with light content sniffing is enough for T1 and avoids building a heavyweight MIME or magic-number subsystem too early.

## Consequences

- `#74` must treat this `RawTransaction` as the upstream producer contract rather than redefining T1 from scratch.
- The CLI will initially be read-only and ingest-only; any persistence or reconciliation behavior remains downstream work.
- CSV support will be intentionally layout-driven rather than heuristic-freeform, so unsupported bank exports will fail validation clearly instead of being parsed opportunistically and incorrectly.
