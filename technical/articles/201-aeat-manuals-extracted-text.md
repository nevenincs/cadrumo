# AEAT manuals, extracted text

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-201` · **Topic:** [Bundled knowledge and localization](../topics/bundled-knowledge-and-localization.md)

<!-- preserved:article -->
## Scope

This reference-data group has 18 large JSON text files totaling 39,162,873 bytes. It includes six IVA manuals (2020–2025), eight IRPF/Renta volumes (part 1 for 2020–2025 plus regional-deduction part 2 for 2024 and 2025), and four Corporate Tax/Sociedades manuals (2022–2025). I inventoried all paths and sizes, parsed the five-field metadata of all 18 records, and read bounded stratified text samples from older and newer IVA, Renta and Sociedades manuals, including the regional volume. The content sample is under the 24,000-token limit; I did not inspect all 39 MB of extracted text or verify legal statements against source PDFs or law.

## Capability and represented knowledge

The files preserve large AEAT practical manuals as normalized text. They are reference material for explaining tax return concepts, annual changes, form fields and filing outcomes. Their stated purpose includes helping taxpayers complete the corresponding forms and disseminating tax information, but the files do not calculate a taxpayer's result, fill in their declaration, or submit it. The 2025 IVA manual covers taxable events, exemptions, special regimes, formal obligations and management, with a front-matter list of changes for 2025 such as VAT rates, billing systems, the EU “VAT in the Digital Age” directive, payment methods and treaty updates. The 2025 Renta manual is split into general and calculation topics, including employment and business income, exemptions, personal/family minimums, deductions and return outcomes. The 2025 Sociedades volume covers corporate taxable base and liability, including the 2025 changes to capital reserve, rates, minimum taxation and free depreciation (IVA 2025 manual (`src/cadrumo/_data/manual_corpus_text/manuals/iva/2025/source.pdf.corpus_text.json`), Renta 2025, part 1 (`src/cadrumo/_data/manual_corpus_text/manuals/renta/2025/part1/source.pdf.corpus_text.json`), Sociedades 2025 (`src/cadrumo/_data/manual_corpus_text/manuals/sociedades/2025/source.pdf.corpus_text.json`)).

There is explicit regional Renta material: the 2024 part-2 volume lists deductions for 15 autonomous communities and is structured around region-specific items such as housing, childbirth/adoption, family status, education and disability. This is materially different knowledge from the national part-1 guide; answers that involve an autonomous deduction must carry both the tax year and region. The 2025 manuals identify publication dates in their text (IVA 2 October 2025, Renta 20 May 2026, Sociedades 10 June 2026), while their tax-year labels remain 2025. These dates are useful freshness signals but do not prove later changes are absent (Renta 2024, autonomous deductions (`src/cadrumo/_data/manual_corpus_text/manuals/renta/2024/part2-deducciones-autonomicas/source.pdf.corpus_text.json`)).

The historical versions are not interchangeable with those recent manuals. The 2020 IVA text itself says the edition closed in September 2020 on the law published up to that date and that subsequent changes applicable to the exercise must be considered. Older manual content can explain a past period, but it is not evidence of a current rule. In the newer manuals, the front matter explicitly says the publication has merely informational effect. Those caveats should remain attached to any derived guidance (IVA 2020 manual (`src/cadrumo/_data/manual_corpus_text/manuals/iva/2020/source.pdf.corpus_text.json`), IVA 2025 manual (`src/cadrumo/_data/manual_corpus_text/manuals/iva/2025/source.pdf.corpus_text.json`)).

A useful cross-inventory detail: the Renta 2024 autonomous-deduction volume is present here as a 1,369,693-byte normalized-text record. The separate source/extraction inventory in STAGE-2-196 noted that this volume lacked its `.extracted.json`/`.extracted.md` sidecars there. Thus the sidecar gap does not mean the project has no machine-readable text for the volume; it has this separate `manual_corpus_text` representation. It still does not establish that all of the normal source-extraction metadata and page structure are available for that part (Renta 2024 part 2 normalized text (`src/cadrumo/_data/manual_corpus_text/manuals/renta/2024/part2-deducciones-autonomicas/source.pdf.corpus_text.json`), [related source/extraction inventory report](196-aeat-practical-manual-corpus.md)).

## Data shape and quality

All 18 JSON documents use schema version 2 and the same keys: `schema_version`, logical `corpus_path`, `source_sha256`, `extraction_platform`, and one large `normalised_text` string. Each identifies `win32` as its extraction platform; all hashes have the expected 64-character hexadecimal shape. The original PDF bytes and acquisition metadata are not in this assigned group, so I did not verify those hashes against the PDFs, publisher URLs or retrieval records. Text lengths range from about 745,000 characters to 4.4 million, with a median near 2 million, so corpus search and reading cost are substantial even though the file count is small.

Normalization preserves readable content and many embedded page headings/dates, but folds Spanish accents and flattens document layout into one string instead of per-page or per-section records. A targeted read found 7,643 U+FFFE noncharacters in the sampled 2020 IVA extraction, including inside ordinary words such as `pu￾blica`; the sample also contains lesser counts in some newer manuals. In context, the character seems to mark a split or extraction boundary, but its source/cause is unverified. Literal search and display can fail around it, and there is no page object in this schema to compare the damaged word with the original. This is a concrete text-quality risk for consumers that treat the normalized string as exact source text; it is not evidence that the underlying PDF is damaged.

## Security and follow-up

These files contain public tax guidance and form explanations, not completed returns. I found no personal taxpayer values in the inspected sections. The manuals discuss highly personal and financial categories, so a product that combines this reference corpus with user data needs separate privacy and authorization review. The JSON records themselves are static text and do not submit filings or enforce the guidance they describe.

The main trust boundaries are tax year, publication date, regional jurisdiction, legal authority and extraction fidelity. Synthesis should trace whether the application indexes or loads these strings, preserves the manuals' informational-effect warnings and year labels, chooses the right regional volume, and handles U+FFFE split tokens. It should also reconcile the distinct extraction representations for Renta 2024 part 2. This chunk does not establish which manuals the product uses, what citations it displays, or whether any calculation matches the manuals.

## Complete assigned-file coverage

- `src/cadrumo/_data/manual_corpus_text/manuals/iva/2020/source.pdf.corpus_text.json` — 1,779,266 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/iva/2021/source.pdf.corpus_text.json` — 748,089 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/iva/2022/source.pdf.corpus_text.json` — 750,548 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/iva/2023/source.pdf.corpus_text.json` — 784,157 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/iva/2024/source.pdf.corpus_text.json` — 834,722 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/iva/2025/source.pdf.corpus_text.json` — 827,209 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/renta/2020/part1/source.pdf.corpus_text.json` — 3,249,187 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/renta/2021/part1/source.pdf.corpus_text.json` — 3,682,746 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/renta/2022/part1/source.pdf.corpus_text.json` — 4,044,963 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/renta/2023/part1/source.pdf.corpus_text.json` — 4,413,073 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/renta/2024/part1/source.pdf.corpus_text.json` — 3,456,904 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/renta/2024/part2-deducciones-autonomicas/source.pdf.corpus_text.json` — 1,369,693 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/renta/2025/part1/source.pdf.corpus_text.json` — 3,406,844 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf.corpus_text.json` — 1,557,330 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/sociedades/2022/source.pdf.corpus_text.json` — 1,952,047 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/sociedades/2023/source.pdf.corpus_text.json` — 2,001,323 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/sociedades/2024/source.pdf.corpus_text.json` — 2,137,876 bytes
- `src/cadrumo/_data/manual_corpus_text/manuals/sociedades/2025/source.pdf.corpus_text.json` — 2,166,896 bytes
<!-- /preserved:article -->
