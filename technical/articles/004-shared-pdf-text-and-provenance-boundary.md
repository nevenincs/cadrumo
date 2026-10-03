# Shared PDF text and provenance boundary

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-004` · **Topic:** [Document and financial imports](../topics/document-and-financial-imports.md)

<!-- preserved:article -->
## Scope

This chunk covers four files (2,979 measured proxy tokens): shared PDF page-text extraction, path redaction, digest-derived provenance, and the reconciliation parser composition adapter. I read all 377 assigned source lines. This is static analysis only; no PDF libraries or reconciliation flows were executed.

## Capabilities and flow

The shared extraction module centralizes pdfplumber access for the borrador, declaration, and receipt parsers. Path extraction returns one stripped text string per page, preserving empty page slots, and raises the caller-supplied error class for missing files, backend failures, or a document with no text layer. The bytes variant opens a `BytesIO` stream and returns the same page tuple without writing source bytes to disk. Two other helpers either concatenate non-empty page text for layout-sensitive receipt extraction or try a caller-supplied fast path before falling back to pdfplumber (page_text_extraction.py (`src/cadrumo/adapters/inbound/pdf/page_text_extraction.py`), page_text_extraction.py (`src/cadrumo/adapters/inbound/pdf/page_text_extraction.py`), page_text_extraction.py (`src/cadrumo/adapters/inbound/pdf/page_text_extraction.py`)).

`redaction.py` defines the shared `<input-pdf>` label for diagnostics. `source_provenance.py` wraps the core chunked SHA-256 helper in a PDF-import error with a redacted path, then constructs `.secure-source/<digest>.pdf` as a persistable reference. It does not create that file, encrypt source bytes, or itself establish secure custody; custody belongs to other layers (source_provenance.py (`src/cadrumo/adapters/inbound/pdf/source_provenance.py`), source_provenance.py (`src/cadrumo/adapters/inbound/pdf/source_provenance.py`)).

`InboundReconciliationEvidenceParser` lazily imports the concrete justificante and declaration parsers when each port method runs. Its path declaration method supplies model, year, and period overrides; its bytes variant also supplies the already-selected registry snapshot and a generic source label. Declaration parser errors are translated to the application reconciliation error. The justificante methods delegate directly. This keeps binding the port lightweight while retaining the underlying parsers’ domain records (reconciliation_parser.py (`src/cadrumo/adapters/inbound/reconciliation_parser.py`), reconciliation_parser.py (`src/cadrumo/adapters/inbound/reconciliation_parser.py`)).

## Data, security, and implementation assessment

The main safety benefit is that decrypted evidence can be extracted from bytes in memory and successful PDF observations can retain digest-derived references instead of the operator’s original filename. Path-based text extraction also uses the common redaction label in its errors. The shared primitive has no local source-byte or page-count cap and materializes every page’s extracted text in memory. That leaves resource limits to callers or library behavior; the assigned code does not demonstrate an upper bound for arbitrary PDF size or page count. The bytes error message incorporates the supplied `source_label` and the backend exception text, whereas the path route reports only the exception type, so callers should keep bytes labels generic if messages may be shown or logged (page_text_extraction.py (`src/cadrumo/adapters/inbound/pdf/page_text_extraction.py`)).

The provenance reference is a name derived from a digest, not evidence that the file exists in an encrypted store. Also, individual path parser flows may hash and parse via separate reads, so this helper alone cannot ensure the digest identifies the exact bytes whose text was extracted if the source path changes between operations. No tests are part of this chunk; other parser modules refer to shared PDF behavior, but static inspection cannot certify pdfplumber behavior on hostile, malformed, or scan-only PDFs.

## Dependencies and follow-up

Synthesis should connect the path/bytes helpers to each format-specific parser, verify where PDF size and page-count limits are imposed, and trace where the `.secure-source` reference is materialized and protected. The reconciliation composition has a path method that relies on the declaration parser’s default registry loading and a bytes method that receives an explicit snapshot; the application port implementation should confirm this split is intentional.

## Complete assigned-file coverage

- pdf/page_text_extraction.py (`src/cadrumo/adapters/inbound/pdf/page_text_extraction.py`) — all 205 lines.
- pdf/redaction.py (`src/cadrumo/adapters/inbound/pdf/redaction.py`) — all 21 lines.
- pdf/source_provenance.py (`src/cadrumo/adapters/inbound/pdf/source_provenance.py`) — all 58 lines.
- reconciliation_parser.py (`src/cadrumo/adapters/inbound/reconciliation_parser.py`) — all 93 lines.
<!-- /preserved:article -->
