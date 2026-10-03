# AEAT practical-manual corpus

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-196` · **Topic:** [Bundled knowledge and localization](../topics/bundled-knowledge-and-localization.md)

<!-- preserved:article -->
## Scope and sampling method

This chunk inventories 124 files totaling 245,309,915 bytes (about 245.3 MB): IVA manuals for 2020–2025, IRPF/Renta manuals for 2020–2025 plus regional-deduction volumes for 2024 and 2025, and Impuesto sobre Sociedades manuals for 2022–2025. The complete inventory is summarized by family below and linked from the manifest-generated appendix. I sampled the 2025 IVA manual, 2024 Renta volumes 1 and 2, and the 2024 Sociedades manual, inspecting small structural indexes and bounded extracted-page metadata rather than reading the full PDFs or their several megabytes of sidecar text.

## Content and retrieval capabilities

Each manual family pairs official AEAT source PDFs and capture manifests with some combination of extracted JSON/Markdown, a short `manual.json` description, a `chapters.json` index, and small structured section summaries. The manifests carry source URLs, capture dates, byte lengths, hashes, edition/year, and a `synthetic: false` flag. In the sampled 2025 IVA, 2024 Renta volume 1, and 2024 Sociedades bundles, the extraction metadata reports `status: ok` and its source hash matches the archived PDF. Their extracted page units make it possible to cite a bounded passage without presenting an entire manual: the sampled files contain 350, 1,558, and 852 page units respectively. Two small Renta 2025 annotation files map topic anchors to selected page numbers and bind those selections to a source hash. This is a useful grounding substrate for manual examples and operator explanations, though no retrieval consumer was inspected here.

The structured navigation is explicitly curated and sparse in this snapshot. Across all 18 manual parts, 16 `chapters.json` files contain one chapter entry and two (Sociedades 2022 and 2023) are empty; there are 16 small section-summary JSON files. All 18 `structure/manual.json` files mark the definition reviewer as `operator`. These are helpful curated entry points, not complete tables of contents or proof that every chapter/rule in the long source is indexed. The Renta 2024 regional-deductions PDF is present with a manifest and a short manual/chapter/section index, but no extracted JSON or Markdown sidecar in this `corpus/manuals` subtree. A separate normalized-text record exists in `manual_corpus_text` (source text asset (`src/cadrumo/_data/manual_corpus_text/manuals/renta/2024/part2-deducciones-autonomicas/source.pdf.corpus_text.json`), analyzed in [STAGE-2-201](201-aeat-manuals-extracted-text.md)); therefore the sidecar gap here does not establish repository-wide absence of machine-readable text. See the IVA 2025 source manifest (`src/cadrumo/_data/corpus/manuals/iva/2025/manifest.json`), IVA 2025 extracted pages (`src/cadrumo/_data/corpus/manuals/iva/2025/source.pdf.extracted.md`), Renta 2024 volume 1 (`src/cadrumo/_data/corpus/manuals/renta/2024/part1/manifest.json`), Renta 2024 regional-deductions volume (`src/cadrumo/_data/corpus/manuals/renta/2024/part2-deducciones-autonomicas/manifest.json`), and Sociedades 2024 manual metadata (`src/cadrumo/_data/corpus/manuals/sociedades/2024/structure/manual.json`).

The data is historical and edition-scoped. Sample capture dates range from May to June 2026; the manuals themselves concern declared tax years 2020–2025. The documents can support an answer about the cited edition, but they should not be treated as a current legal authority without confirming the relevant filing year, later amendments, and the exact cited pages. A source URL/hash confirms what the bundle says it captured, not whether the source remains current or whether text extraction preserved every table and footnote.

## Assessment and limitations

The strongest property is traceability: the source PDF is retained alongside extracted text, per-page units, hashes, and a small human-authored topic index. The distinction between source and curated metadata matters. The structure summaries can direct a search, while the PDF/page extraction remains necessary to ground a claim. Sparse chapter indexing and the missing source-sidecar in this subtree limit this file set for retrieval. A separate normalized-text record exists as noted above; how retrieval uses it is outside this chunk.

These are reference documents, not executable filing logic. No personal case files or credentials were reviewed, though the manuals themselves include worked examples. PDFs and extracted text are treated as data only; parser safety, extraction completeness, and legal correctness were not tested. No application was run and no code was modified.

| Family | Files | Bytes | Edition coverage |
| --- | ---: | ---: | --- |
| IVA manuals | 42 | 41,819,576 | 2020–2025 |
| Renta manuals | 56 | 155,084,171 | 2020–2025; regional-deduction volumes in 2024–2025 |
| Sociedades manuals | 26 | 48,406,168 | 2022–2025 |
| **Total** | **124** | **245,309,915** | |

## Complete assigned-file inventory

The 124 source links below cover the chunk manifest. Inventory coverage is complete; semantic inspection is limited to the samples above.
- `src/cadrumo/_data/corpus/manuals/iva/2020/manifest.json` — 407 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2020/source.pdf` — 4765246 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2020/source.pdf.extracted.json` — 1893382 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2020/source.pdf.extracted.md` — 1811541 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2020/structure/chapters.json` — 343 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2020/structure/manual.json` — 519 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2020/structure/sections/cap1/sec1.json` — 847 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2021/manifest.json` — 405 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2021/source.pdf` — 1953133 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2021/source.pdf.extracted.json` — 804571 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2021/source.pdf.extracted.md` — 764448 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2021/structure/chapters.json` — 343 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2021/structure/manual.json` — 517 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2021/structure/sections/cap1/sec1.json` — 845 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2022/manifest.json` — 407 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2022/source.pdf` — 5042176 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2022/source.pdf.extracted.json` — 806203 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2022/source.pdf.extracted.md` — 766899 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2022/structure/chapters.json` — 343 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2022/structure/manual.json` — 519 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2022/structure/sections/cap1/sec1.json` — 847 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2023/manifest.json` — 407 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2023/source.pdf` — 5421056 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2023/source.pdf.extracted.json` — 842771 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2023/source.pdf.extracted.md` — 801251 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2023/structure/chapters.json` — 343 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2023/structure/manual.json` — 519 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2023/structure/sections/cap1/sec1.json` — 847 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2024/manifest.json` — 407 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2024/source.pdf` — 6348800 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2024/source.pdf.extracted.json` — 899331 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2024/source.pdf.extracted.md` — 853086 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2024/structure/chapters.json` — 343 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2024/structure/manual.json` — 519 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2024/structure/sections/cap1/sec1.json` — 847 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2025/manifest.json` — 407 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2025/source.pdf` — 6296576 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2025/source.pdf.extracted.json` — 891016 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2025/source.pdf.extracted.md` — 845437 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2025/structure/chapters.json` — 323 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2025/structure/manual.json` — 503 bytes
- `src/cadrumo/_data/corpus/manuals/iva/2025/structure/sections/cap1/sec1.json` — 846 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2020/part1/manifest.json` — 419 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2020/part1/source.pdf` — 32387072 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2020/part1/source.pdf.extracted.json` — 3514036 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2020/part1/source.pdf.extracted.md` — 3326790 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2020/part1/structure/chapters.json` — 312 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2020/part1/structure/manual.json` — 528 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2020/part1/structure/sections/cap1/sec1.json` — 758 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2021/part1/manifest.json` — 419 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2021/part1/source.pdf` — 26314752 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2021/part1/source.pdf.extracted.json` — 3967412 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2021/part1/source.pdf.extracted.md` — 3769377 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2021/part1/structure/chapters.json` — 312 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2021/part1/structure/manual.json` — 528 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2021/part1/structure/sections/cap1/sec1.json` — 758 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2022/part1/manifest.json` — 418 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2022/part1/source.pdf` — 9706572 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2022/part1/source.pdf.extracted.json` — 4357498 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2022/part1/source.pdf.extracted.md` — 4139951 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2022/part1/structure/chapters.json` — 312 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2022/part1/structure/manual.json` — 528 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2022/part1/structure/sections/cap1/sec1.json` — 758 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2023/part1/manifest.json` — 419 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2023/part1/source.pdf` — 11604722 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2023/part1/source.pdf.extracted.json` — 4768652 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2023/part1/source.pdf.extracted.md` — 4518545 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2023/part1/structure/chapters.json` — 312 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2023/part1/structure/manual.json` — 528 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2023/part1/structure/sections/cap1/sec1.json` — 758 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2024/part1/manifest.json` — 423 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2024/part1/source.pdf` — 9214502 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2024/part1/source.pdf.extracted.json` — 3742651 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2024/part1/source.pdf.extracted.md` — 3539119 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2024/part1/structure/chapters.json` — 312 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2024/part1/structure/manual.json` — 533 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2024/part1/structure/sections/cap1/sec1.json` — 763 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2024/part2-deducciones-autonomicas/manifest.json` — 478 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2024/part2-deducciones-autonomicas/source.pdf` — 3404339 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2024/part2-deducciones-autonomicas/structure/chapters.json` — 320 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2024/part2-deducciones-autonomicas/structure/manual.json` — 635 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2024/part2-deducciones-autonomicas/structure/sections/cap1/sec1.json` — 832 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/manifest.json` — 432 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf` — 8554799 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.annotation.json` — 609 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.json` — 3676254 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md` — 3486623 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/structure/chapters.json` — 312 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/structure/manual.json` — 534 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/structure/sections/cap1/sec1.json` — 764 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/manifest.json` — 472 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf` — 3801341 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf.annotation.json` — 267 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf.extracted.json` — 1677252 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf.extracted.md` — 1594333 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/structure/chapters.json` — 334 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/structure/manual.json` — 609 bytes
- `src/cadrumo/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/structure/sections/cap1/sec1.json` — 883 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2022/manifest.json` — 422 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2022/source.pdf` — 14432256 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2022/source.pdf.extracted.json` — 2096284 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2022/source.pdf.extracted.md` — 1998173 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2022/structure/chapters.json` — 3 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2022/structure/manual.json` — 529 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2023/manifest.json` — 421 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2023/source.pdf` — 5188800 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2023/source.pdf.extracted.json` — 2153112 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2023/source.pdf.extracted.md` — 2048897 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2023/structure/chapters.json` — 3 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2023/structure/manual.json` — 529 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2024/manifest.json` — 421 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2024/source.pdf` — 6266062 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2024/source.pdf.extracted.json` — 2299823 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2024/source.pdf.extracted.md` — 2188412 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2024/structure/chapters.json` — 336 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2024/structure/manual.json` — 529 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2024/structure/sections/cap1/sec1.json` — 808 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2025/manifest.json` — 421 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2025/source.pdf` — 5178589 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2025/source.pdf.extracted.json` — 2331546 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2025/source.pdf.extracted.md` — 2218119 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2025/structure/chapters.json` — 336 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2025/structure/manual.json` — 529 bytes
- `src/cadrumo/_data/corpus/manuals/sociedades/2025/structure/sections/cap1/sec1.json` — 808 bytes
<!-- /preserved:article -->
