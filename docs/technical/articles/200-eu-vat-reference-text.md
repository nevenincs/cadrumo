# EU VAT reference text

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-200` · **Topic:** [Bundled knowledge and localization](../topics/bundled-knowledge-and-localization.md)

<!-- preserved:article -->
## Scope

This group contains two extracted PDF text records totaling 64,775 bytes. I parsed both completely as JSON and sampled the introduction, tables and dated rate-change passages in their `normalised_text` fields; the semantic sample is within the 24,000-token cap. No original PDFs or application consumer are included here, and I did not verify the source statements against current law.

## Capability and content

The two records offer different reference roles. The EPRS briefing, titled “Highs and lows; VAT rate-setting in the European Union,” is dated January 2026 and explains the EU framework for member states' standard, reduced, super-reduced and zero VAT rates. It gives a high-level legal overview, describes policy tradeoffs and includes comparative tables. The briefing says a standard rate must be at least 15%, and that reduced rates are optional, with EU rules limiting their use to listed categories. It also states that its overview omits super-reduced and “parking” rates and some territorial/legal derogations, a useful qualification against reading its tables as complete legal treatment (EPRS VAT briefing extraction (`src/cadrumo/_data/manual_corpus_text/eu_official/iva/eprs-iva-rates-eu-2025-07-01.pdf.corpus_text.json`)).

Its filename includes `2025-07-01`; the text explains this is the date the EU rate database table was last updated. The briefing is labeled January 2026, while its standard/reduced-rate table is a 1 July 2025 snapshot and expressly notes Romania's standard-rate increase from 19% to 21% on 1 August 2025. The two dates describe different things. A downstream answer that reports a rate needs the table's as-of date and the later Romanian amendment, rather than treating the entire briefing as a single timeless table. Its annexed figures also include estimated 2022 VAT-gap values, which are historical statistics, not current rate or obligation data.

The Romanian record is a short public-finance administration notice dated 7 August 2025 about Law 141/2025, published 25 July. It summarizes the standard-rate move from 19% to 21% and reduced rate of 11% effective 1 August, lists product/service categories affected by rate changes, and describes transitional treatment for some VAT exemptions. It serves as a country-specific update and supplies more detail for affected categories than the EPRS comparison table. These are statements found in the source extraction, not independently confirmed legal advice (Romanian ANAF notice extraction (`src/cadrumo/_data/manual_corpus_text/eu_official/iva/romania-iva-rate-change-2025.pdf.corpus_text.json`)).

## Data shape and quality

Both files use the same five-field schema: `schema_version` 2, logical `corpus_path`, `source_sha256`, `extraction_platform` (`win32`), and one flattened `normalised_text` string. The strings contain 43,650 and 20,522 characters respectively. Their 64-character source digests are present, but the original PDFs and acquisition records are outside this assignment, so the digest-to-source binding, publisher, retrieval date and extraction tool/version could not be checked here. No page array or table-cell structure is retained.

The flattened text remains useful for search and narrative reading, but it weakens precise comparisons when tables are involved: the EU rate table and revenue table become sequences of country names, rates and values without machine-readable rows/columns. A targeted check also found one U+FFFE noncharacter inside `higher￾income` in the EPRS text, splitting a search term. That is a confirmed local extraction artifact; its practical effect depends on whether a consumer performs exact matching or displays the text. Other labels and values are not validated against page images in this chunk.

## Security and follow-up

The sampled text contains public policy research and tax-administration material; I found no taxpayer submissions, credentials or active code. It has no runtime behavior or direct filing capability. The main trust concerns are legal authority, jurisdiction, effective date and extraction fidelity. EPRS is secondary analysis with explicit scope limits; the Romanian document is a dated local administrative summary. Synthesis should trace whether the product uses one or both, preserves jurisdiction and date qualifications, and resolves conflicting or later official rates before presenting user-specific guidance. No test, source-download or live verification is part of this chunk.

## Complete assigned-file coverage

- `src/cadrumo/_data/manual_corpus_text/eu_official/iva/eprs-iva-rates-eu-2025-07-01.pdf.corpus_text.json` — 44,016 bytes
- `src/cadrumo/_data/manual_corpus_text/eu_official/iva/romania-iva-rate-change-2025.pdf.corpus_text.json` — 20,759 bytes
<!-- /preserved:article -->
