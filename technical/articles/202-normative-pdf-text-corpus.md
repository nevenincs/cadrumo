# Normative PDF text corpus

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-202` · **Topic:** [Bundled knowledge and localization](../topics/bundled-knowledge-and-localization.md)

<!-- preserved:article -->
## Scope

This group contains four extracted PDF text records totaling 290,575 bytes. They correspond to the 2003 Modelo 185 annex, the 2023 Modelo 721 order/layout, its 2024 amendment, and the 2026 VAT-model amendment/order. I read bounded samples from each record's normalized text and parsed all four metadata records. I also checked each `source_sha256` against the corresponding PDF in `src/cadrumo/_data/corpus/normatives/pdf`; all four hashes matched. This confirms these text records are pinned to the bundled PDFs, not that either the source or its legal content is complete or current.

## Capability and knowledge represented

These files preserve form-layout and legal-instrument text for downstream reference/search. The 2023 Modelo 721 text describes the informational declaration on virtual currency held abroad and includes field definitions such as the year-end balance, currency origin, identifier type and the status/date when a person ceases to be a holder or authorized person. The 2024 order amends multiple information models, including 721, and its sampled layout text describes currency type/value and holder fields. Those fields imply the subject matter can involve financial holdings and identity documents, but the bundled files are schema text, not completed declarations or customer data (2023 Modelo 721 order (`src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2023-17429-modelo-721-layout.pdf.corpus_text.json`), 2024 amendment text (`src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2024-27528-modelo-721-layout-amendment.pdf.corpus_text.json`)).

The 2026 record contains Order HAC/27/2026 and technical changes to VAT models 303, 322, 353 and 390, including their associated electronic VAT-book specifications. This is regulatory and record-layout material, not a live model form or submission endpoint. It overlaps the raw PDF and extraction artifacts described in STAGE-2-197; synthesis should connect these representations without counting them as separate legal sources (2026 VAT-model order text (`src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2026-1761-modelo-390-form.pdf.corpus_text.json`), [related raw normative corpus report](197-normative-reference-corpus.md)).

The 2003 record begins with Order HAC/96/2003 and a Modelo 185 information schema: monthly information that Social Security management bodies and mutual societies must provide about affiliates or members, with machine-readable and telematic filing procedures. The extracted text later contains a section on telematic job-posting procedures in the Ministry of Economy. That is visibly unrelated to the Modelo 185 field specification; because this representation has no page objects, I cannot tell whether the captured PDF intentionally includes adjacent BOE matter or whether extraction scope bled across a document boundary. A consumer should not assume that every paragraph in this flattened record belongs to Modelo 185 (2003 Modelo 185 text (`src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2003-1911-modelo-185-annex-i.pdf.corpus_text.json`)).

## Data quality and trust boundaries

All four JSON records have the same five-field schema-v2 shape: logical `corpus_path`, source SHA-256, `extraction_platform` (`win32`), and one `normalised_text` string in addition to the schema version. The logical paths bind to the four local PDFs and all digests match. Unlike the page-oriented `.extracted.json` representation of the Modelo 390 source, these records flatten each PDF's text into one string. Page numbers are present as text in places, but there is no page-level boundary or table structure. Normalization also retains some extraction markers: the 2003 Modelo 185 text contains 83 U+FFFE noncharacters, and the 2026 390 text has seven plus 29 private-use characters, including markers adjacent to field flags. The visual meaning of those private-use characters cannot be recovered from this text alone. These are concrete fidelity limits for exact search, display or automated parsing; the matching source hashes make rechecking possible against the bundled PDF.

## Security and follow-up

The reviewed assets are public legal and form-layout documents with no filled taxpayer values or credentials. The formats are static JSON text; they do not collect or transmit user data, enforce authorization, perform calculations or submit filings. A product that lets users provide the financial and identity details described in these layouts would need separate privacy and validation controls; those flows are outside this chunk. Synthesis should trace whether consumers prefer the matching source PDF, the page-oriented extraction, or this flattened corpus text, and how they preserve model version/effective dates and exclude the unrelated-looking Modelo 185 passage. No runtime or law verification was performed.

## Complete assigned-file coverage

- `src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2003-1911-modelo-185-annex-i.pdf.corpus_text.json` — 34,058 bytes
- `src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2023-17429-modelo-721-layout.pdf.corpus_text.json` — 21,200 bytes
- `src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2024-27528-modelo-721-layout-amendment.pdf.corpus_text.json` — 88,905 bytes
- `src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2026-1761-modelo-390-form.pdf.corpus_text.json` — 146,412 bytes
<!-- /preserved:article -->
