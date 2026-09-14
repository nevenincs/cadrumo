---
tags:
  - '#audit'
  - '#registry-corpus-pruning'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:cdfcae254981adedddba3a7a34f335b8d8966549f4de18f6d0aabf5c55b6d4ef'
related:
  - "[[2026-09-14-registry-corpus-pruning-ownership-reference]]"
---
# `registry-corpus-pruning` audit: `Pruning verification`

## Scope

Reviewed the correction-annotation catalogue integration, six removed corpus artefacts, Modelo 720 source comments and provenance, and one regenerated Markdown derivative. Concurrent authority compiler and runtime edits were excluded.

## Findings

### correction-provenance | low | Historical inspection locators outlive their binaries

The retained Modelo 100 XLS corrections cite a historical 2017 XLSX inspection and describe both encodings. These are not current-file claims that can safely be rewritten by changing extensions. The operative corrections match the removed annotations. The additional 2016 explanation about the unaffected Comp column was preserved in the retained annotation. Historical grounding-locator standardization remains open.

### extraction-owner | medium | Full extraction regeneration encounters an existing annual-Orden refusal

The broad test run returned 26 passed and 2 failed. The generic sidecar failure was an extra EOF newline in `orden-hfp-1335-2021.html.extracted.md`; the owning extractor removed exactly one byte, leaving source and typed JSON unchanged. A subsequent record-design support and generic freshness run passed all 25 tests. The other failure remains: `test_enrolled_html_and_workbook_sidecars_match_the_owner_check` raises `OrdenAnualHtmlParseError` for `orden-hac-1347-2024.html`, reporting incomplete municipal IVA reduction clauses. Direct regeneration of that unchanged input reproduces the refusal. The source and annual-Orden parser were not changed by this cleanup.

### pruning-proof | low | Scoped pruning is verified, not blanket corpus retirement

Six deleted files total 738723 bytes. The Modelo 720 PDF and Markdown twins are byte-identical; extracted units and normalized runtime text are equal. The registry TOML remains typed-equal. No remaining deleted-filename references were found in source, tooling or user documentation. All 140 remaining runtime corpus-text files resolve to existing sources. The 2247 tracked registry files contain no empty files or extensions outside TOML and JSON. Locks and bytecode were not deleted. The independent review found no blocking issue.

## Recommendations

Keep the existing corpus checker responsible for exact correction targets. Preserve actively consumed Renta overlays, the formula-bearing Modelo 200 workbook, GROI fixtures, historical retirement evidence and per-edition manual structures until their consumers and provenance can move atomically. Investigate the annual-Orden extraction refusal without weakening its legal-evidence contract. Ruff lint, format checks and scoped diff whitespace checks pass.
