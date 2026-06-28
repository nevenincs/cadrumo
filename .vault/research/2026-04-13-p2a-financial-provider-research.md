---
tags:
  - "#research"
  - "#p2a-financial-provider"
date: "2026-04-13"
modified: '2026-04-13'
related:
  - "[[2026-04-12-base-module-structure-adr]]"
  - "[[2026-04-12-base-module-structure-reference]]"
---

# `p2a-financial-provider` research: `tdp-t1-financial-ingest`

This research grounds issue `#73` within TDP step `T1` from issue `#104`. The goal is to emit strict `RawTransaction` records from file-based providers while preserving byte-level provenance and staying inside the established `src/aeat/` subpackage conventions.

## Findings

### TDP contract and repo constraints

- Issue `#73` is explicitly a `T1 — Ingest` step: file inputs in, `RawTransaction` out, with the provenance chain preserved back to the source document.
- Issue `#104` defines the non-negotiable invariant: every downstream record must be traceable back to its raw source through `source_path`, content hash, and source position.
- Issue `#74` is not on `main`, so the safe boundary is to define the concrete `RawTransaction` producer model in this issue and keep cross-step references out of the implementation surface.
- The repo already standardizes on strict frozen pydantic v2 models, `enum.StrEnum` for closed sets, Typer for CLI, `aeat.core.errors.AeatError` for domain exceptions, `aeat.core.logging.get_logger(__name__)` for logging, and colocated pytest modules marked `@pytest.mark.unit` or `@pytest.mark.live`.

### OFX format research

- The OFX bank statement transaction block is centered on `BANKTRANLIST` and repeated `STMTTRN` entries.
- The fields consistently surfaced across OFX guidance and exporters are `DTPOSTED`, `TRNAMT`, `FITID`, `NAME`, and `MEMO`; these are sufficient to build a stable `RawTransaction` without inventing bank-specific parsing rules.
- `FITID` is the best available provider-issued transaction identifier when present; when absent, the fallback must be a deterministic synthetic identifier based on source hash and row index.
- OFX date values are often `YYYYMMDD` or `YYYYMMDDHHMMSS` with optional timezone suffixes, so the parser should normalize by truncating to the leading date component for T1 ingest.

Sources:
https://www.ofx.net/
https://inte.oldnational.com/498aff/globalassets/onb-site/onb-documents/onb-business/onb-business-tmic/onpointe-file-export-spec-guide.pdf

### Common Spanish bank CSV export layouts

- Spanish retail-bank exports are usually semicolon-delimited and use European decimal formatting (`1.234,56`), while Revolut CSV exports are comma-delimited and use dot decimals (`1234.56`).
- BBVA exports commonly expose operation date, value date, concept/description, amount, balance, and optional currency columns. The stable alias set is `Fecha operación`, `Fecha valor`, `Concepto`, `Importe`, `Saldo`, `Moneda`.
- Santander exports commonly expose `Fecha`, `Fecha valor`, `Concepto`, `Importe`, `Divisa`, `Saldo`. Date values are day-first (`dd/mm/yyyy`) and the delimiter is typically `;`.
- CaixaBank exports commonly expose movement date, value date, concept, amount, and balance under aliases such as `Fecha`, `Fecha movimiento`, `Fecha valor`, `Concepto`, `Importe`, `Saldo`.
- Revolut statement CSV is structurally different: `Type`, `Product`, `Started Date`, `Completed Date`, `Description`, `Amount`, `Fee`, `Currency`, `State`, `Balance`. The documented date-time format is `yyyy-MM-dd hh:mm:ss`, delimiter `,`, and the currency is explicit per row.
- Because the four layouts differ mainly in header names, date formats, decimal separators, and whether a currency column is present, the most robust approach is a provider-internal per-bank column-map model with alias sets rather than one parser per bank.

Sources:
https://www.checkfin.co.uk/bank-statement-converters/bbva/
https://www.checkfin.co.uk/bank-statement-converters/santander/
https://www.ibercaja.es/particulares/digitalizacion/aplicaciones-banca-digital/todas-las-aplicaciones/excel-para-la-gestion-de-tus-cuentas/
https://awesome.ecosyste.ms/projects/github.com%2Fmincong-h%2Ffinance-toolkit
https://help.revolut.com/en-CZ/business/help/managing-my-business/viewing-my-account-statements/finding-my-account-statement/

### Encoding and dialect handling

- CSV imports cannot assume UTF-8. Spanish bank exports frequently arrive as `cp1252` or `ISO-8859-1`, especially when accented headers such as `Fecha operación` are present.
- The safest T1 validation flow is: read bytes once, compute SHA-256 once, attempt decode in a fixed encoding order, then sniff dialect on a representative sample using stdlib `csv.Sniffer`.
- Validation needs to return the winning encoding and a compact dialect description so the CLI can explain how the source was interpreted before ingesting rows.

### XLSX handling with `openpyxl`

- `openpyxl.load_workbook(..., read_only=True, data_only=True)` is the right read path for ingest because it avoids editing concerns, streams worksheet rows, and returns computed cell values instead of formulas.
- Header-row detection should not assume the first row is the header. A short scan over the first several rows is enough to find the row that best matches the known column aliases.
- XLSX date cells can already be typed as `datetime`/`date` objects by `openpyxl`, so the T1 parser should accept both typed dates and string-formatted dates without lossy coercion.

Sources:
https://openpyxl.readthedocs.io/en/3.1/api/openpyxl.reader.excel.html

### File-format auto-detection

- Extension-first detection is sufficient for the happy path: `.csv` -> CSV provider, `.xlsx` -> XLSX provider, `.ofx`/`.qfx` -> OFX provider.
- Content sniffing is still needed for ambiguous or mismatched extensions: ZIP magic (`PK`) implies XLSX, `<OFX>` or SGML-style OFX tags imply OFX, and delimited text with bank-layout headers implies CSV.
- Detection should return a provider instance, not a provider kind enum, because the CLI and future sibling connectors need the behavior surface directly.

### Recommended implementation direction

- Create `src/aeat/domain/financial/` as the public Phase 2 entry point and keep all implementation modules underscored except public re-exports.
- Define `RawTransaction`, `RawProvenance`, `SourceFormat`, and `ProviderValidation` as strict frozen pydantic v2 models with `extra="forbid"`.
- Keep the provider surface synchronous for file imports: `can_handle`, `validate_source`, `ingest`.
- Use deterministic synthetic transaction IDs when no external ID exists: hash prefix + source row index is enough for T1 and does not pre-empt the richer catalogue logic planned for `#74`.
- Add `openpyxl` and `ofxparse` explicitly to `pyproject.toml`; neither is guaranteed by the current dependency tree.
