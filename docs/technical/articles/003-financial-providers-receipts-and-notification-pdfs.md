# Financial providers, receipts, and notification PDFs

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-003` · **Topic:** [Document and financial imports](../topics/document-and-financial-imports.md)

<!-- preserved:article -->
## Scope

This chunk covers 22 files (47,191 measured proxy tokens) across financial statement providers, AEAT filing receipts, notification acts, and shared PDF parsing primitives. I read every assigned file in full, splitting the longer provider and extractor files into bounded ranges. This is static inspection only; I did not execute parsers or inspect the referenced tests and external provider libraries.

## Product capabilities and flows

The financial provider base defines source validation, structured errors, raw provenance, date and decimal parsing, and the rule that a bank movement’s sign is converted once into an explicit incoming/outgoing direction while its stored amount becomes a positive magnitude. It refuses zero-value ledger movements. Provider input helpers refuse symlinks, missing/non-file paths, and files over 64 MiB before reading source bytes. A common provenance record stores resolved source path, SHA-256, row number, format, provider, and ingestion time (base.py (`src/cadrumo/adapters/inbound/financial/providers/base.py`), base.py (`src/cadrumo/adapters/inbound/financial/providers/base.py`), base.py (`src/cadrumo/adapters/inbound/financial/providers/base.py`)).

Auto-detection orders fixed-layout providers using extension hints and file signatures, then appends the mapped-tabular fallback. CSV supports N26, BBVA, Santander, CaixaBank, and Revolut header aliases; it scans up to ten rows for a header, rejects AEAT ledger-export headers, and parses dates, signed amounts or explicit direction, currency, descriptions, counterparties, and source IDs. Missing source IDs are synthesized from provider, content digest, and row index. CSV ingest raises on a malformed transaction row. OFX/QFX reads every statement block, copies OFX-native fields, and uses transaction IDs or account-specific synthetic IDs. The optional `ofxtools` dependency is loaded lazily because it is GPL-only; a clearly OFX source without the optional extra receives a typed missing-extra error. N26 PDF reads a German-language statement table and attaches continuation lines such as value dates and remittance notes to the preceding transaction. XLS/XLSX select the worksheet and header row that best match the CSV bank-layout catalogue, preserve typed workbook cells, and refuse formula cells in selected data rows rather than trusting cached formula values (detection.py (`src/cadrumo/adapters/inbound/financial/providers/detection.py`), csv.py (`src/cadrumo/adapters/inbound/financial/providers/csv.py`), ofx.py (`src/cadrumo/adapters/inbound/financial/providers/ofx.py`), pdf_n26.py (`src/cadrumo/adapters/inbound/financial/providers/pdf_n26.py`), xlsx.py (`src/cadrumo/adapters/inbound/financial/providers/xlsx.py`)).

The justificante route reads receipt metadata rather than casilla values: AEAT CSV, model, tax period and exercise year, filer NIF, presentation timestamp, optional payment totals and presentation ID, plus a verification URL. Regex tiers handle Spanish and English labels, accented and unaccented text, and older value-before-label layouts. Money is parsed with `Decimal`; ambiguous thousands-versus-decimal shapes fail instead of becoming plausible wrong totals. Required fields and the final strict `Justificante` model are validated, with structured missing/malformed/ambiguous error attributes. The path route hashes the source and redacts caller paths from errors when detected; the bytes route parses decrypted content in memory and avoids plaintext scratch files (justificante/parser.py (`src/cadrumo/adapters/inbound/justificante/parser.py`), justificante/_extract.py (`src/cadrumo/adapters/inbound/justificante/_extract.py`)). Path extraction caches up to 256 concatenated text results by content digest, backend, file size, and modification time; the bytes route is uncached (text_extraction.py (`src/cadrumo/adapters/inbound/justificante/_parsers/text_extraction.py`)).

The notification reader accepts already-fetched PDF bytes through an application port, extracts page text, and returns either a complete typed sanction/liquidation record or a bounded refusal reason. Its deterministic parser resolves text IDs, printed amounts and percentages, and statutory reduction-label values from a generation-pinned registry facts operation. Repeated equal values collapse; conflicting repeats refuse. Before returning, it checks that the printed base times percentage reproduces the sanction and that the sanction minus reductions reproduces the payable within one cent (document_reader.py (`src/cadrumo/adapters/inbound/notificacion/document_reader.py`), sancion.py (`src/cadrumo/adapters/inbound/notificacion/sancion.py`), sancion.py (`src/cadrumo/adapters/inbound/notificacion/sancion.py`)). A direct parse defaults the reduction fact date to today in Madrid time; the notification reader passes today explicitly, so synthesis should verify that this date axis matches the legal date applicable to historical acts (sancion.py (`src/cadrumo/adapters/inbound/notificacion/sancion.py`)).

Shared PDF helpers define strict casilla observations, standard AEAT labels and amount regexes, and Spanish decimal parsing. The amount regex requires a comma and two decimal digits and recognizes dot, NBSP, and narrow-NBSP thousands separators. The more permissive decimal parser also accepts already-delimited US-style input, but rejects non-finite decimals (label_regex.py (`src/cadrumo/adapters/inbound/pdf/label_regex.py`), label_regex.py (`src/cadrumo/adapters/inbound/pdf/label_regex.py`)). `ExtractedCasilla` carries a typed value, source page, optional bounding box, and bounded confidence score.

## Knowledge, data, and trust

Financial statement values and raw source fields are retained in `RawTransaction` records with provenance; account names, counterparties, descriptions, and identifiers can be personal or commercially sensitive. Corpus declarations are explicit class attributes. The OFX and CSV providers declare synthetic fixtures derived from published format material; N26’s documented corpus is generated from published statement text and is not exhaustive. The base class enforces that each concrete provider declares a verification source and provisional-specimen flag at class definition. Its comments say test-suite checks also enforce the policy, but those tests are outside this chunk and were not independently verified.

The receipt parser reads what the document states; it does not contact AEAT to validate the CSV or verify that the extracted URL belongs to AEAT. `AnyHttpUrl` checks URL syntax, not destination trust. The notification parser’s reduction percentages come from the governed-fact authority rather than literals embedded in the parser; the label text remains local vocabulary. However, the notification reader supplies the current Madrid date rather than a date extracted from the act, so historical applicability is an unresolved authority question. No assigned module persists these records.

## Security and implementation assessment

The financial base’s 64 MiB cap and symlink check provide useful input guards, and formula cells are refused in selected spreadsheet data rows. However, the cap is not consistently applied before validation: auto-detection reads `path.read_bytes()[:256]` for unknown suffixes, which loads the whole file before slicing, while OFX, N26 PDF, and XLSX validation enter their parsers directly from a path before calling the shared byte-reading guard. An oversized file can therefore be loaded or parsed before the advertised limit rejects it (detection.py (`src/cadrumo/adapters/inbound/financial/providers/detection.py`), ofx.py (`src/cadrumo/adapters/inbound/financial/providers/ofx.py`), pdf_n26.py (`src/cadrumo/adapters/inbound/financial/providers/pdf_n26.py`), xlsx.py (`src/cadrumo/adapters/inbound/financial/providers/xlsx.py`)). This is a confirmed local resource-boundary gap. CSV parses and hashes the same in-memory bytes; OFX, N26 PDF, XLS, and XLSX compute a source digest and then parse by reopening the path. If the source changes between those reads, parsed content and provenance digest can diverge. That is conditional on concurrent file replacement, but worth checking in workflows that ingest mutable paths.

The N26 and spreadsheet fixture declarations are described as synthetic. N26’s module explicitly says that current generated samples do not cover every account or FX variant, so correctness against all supported statement kinds is not established by the assigned code. `parse_sancion_document` also classifies an act as a sanction if normalized text contains the word “sancion,” otherwise as a liquidation; this vocabulary rule is simple and should be checked against real mixed-reference documents. The receipt URL matcher accepts the first HTTP(S) URL and does not constrain the host, which is safe only if downstream code treats it as untrusted data. Notification parsing itself does not fetch, persist, or navigate to external resources.

Error handling is generally explicit: financial parsers distinguish invalid source, validation, and optional-extra failures; justificante and sanction errors preserve structured field classifications; sanction records fail closed on incomplete or conflicting evidence and arithmetic mismatch. The source tree refers to fixture and detection tests, but no tests are assigned here and none were run. Static reading cannot establish extraction accuracy against PDFs, optional-extra behavior, or the legal accuracy of the bundled reduction facts.

## Dependencies and follow-up

Synthesis should connect the financial provider adapter to application ledger persistence and error presentation; check column mapping, currency settings, and source-path exposure; inspect the notification outbound gate and date used for governed reduction facts; and confirm what downstream code does with receipt verification URLs. It should also verify that content digests correspond to the exact bytes parsed when file paths can change during ingest.

## Complete assigned-file coverage

- financial/providers/_tabular_projection.py (`src/cadrumo/adapters/inbound/financial/providers/_tabular_projection.py`) — all 236 lines.
- financial/providers/base.py (`src/cadrumo/adapters/inbound/financial/providers/base.py`) — all 819 lines, read in two ranges.
- financial/providers/csv.py (`src/cadrumo/adapters/inbound/financial/providers/csv.py`) — all 711 lines, read in two ranges.
- financial/providers/detection.py (`src/cadrumo/adapters/inbound/financial/providers/detection.py`) — all 95 lines.
- financial/providers/ofx.py (`src/cadrumo/adapters/inbound/financial/providers/ofx.py`) — all 378 lines.
- financial/providers/pdf_n26.py (`src/cadrumo/adapters/inbound/financial/providers/pdf_n26.py`) — all 377 lines.
- financial/providers/workbook_layout.py (`src/cadrumo/adapters/inbound/financial/providers/workbook_layout.py`) — all 145 lines.
- financial/providers/xls.py (`src/cadrumo/adapters/inbound/financial/providers/xls.py`) — all 142 lines.
- financial/providers/xlsx.py (`src/cadrumo/adapters/inbound/financial/providers/xlsx.py`) — all 305 lines.
- justificante/__init__.py (`src/cadrumo/adapters/inbound/justificante/__init__.py`) — all 26 lines.
- justificante/_extract.py (`src/cadrumo/adapters/inbound/justificante/_extract.py`) — all 559 lines, read in two ranges.
- justificante/_parsers/__init__.py (`src/cadrumo/adapters/inbound/justificante/_parsers/__init__.py`) — all 19 lines.
- justificante/_parsers/_pdfplumber_backend.py (`src/cadrumo/adapters/inbound/justificante/_parsers/_pdfplumber_backend.py`) — all 55 lines.
- justificante/_parsers/text_extraction.py (`src/cadrumo/adapters/inbound/justificante/_parsers/text_extraction.py`) — all 102 lines.
- justificante/parser.py (`src/cadrumo/adapters/inbound/justificante/parser.py`) — all 157 lines.
- notificacion/__init__.py (`src/cadrumo/adapters/inbound/notificacion/__init__.py`) — all 24 lines.
- notificacion/document_reader.py (`src/cadrumo/adapters/inbound/notificacion/document_reader.py`) — all 45 lines.
- notificacion/errors.py (`src/cadrumo/adapters/inbound/notificacion/errors.py`) — all 82 lines.
- notificacion/sancion.py (`src/cadrumo/adapters/inbound/notificacion/sancion.py`) — all 624 lines.
- pdf/__init__.py (`src/cadrumo/adapters/inbound/pdf/__init__.py`) — all 38 lines.
- pdf/extracted_casilla.py (`src/cadrumo/adapters/inbound/pdf/extracted_casilla.py`) — all 53 lines.
- pdf/label_regex.py (`src/cadrumo/adapters/inbound/pdf/label_regex.py`) — all 144 lines.
<!-- /preserved:article -->
