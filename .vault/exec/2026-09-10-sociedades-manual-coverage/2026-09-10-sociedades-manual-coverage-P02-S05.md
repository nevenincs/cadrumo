---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:649f5942a0928d1d939fdd993fdf3a60b99fa204338ad8da4aeb2c6f4dc622d2'
step_id: 'S05'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---
# Acquire and extract the official 2022 and 2023 Sociedades manual artefacts with provenance sidecars

## Scope

- `src/cadrumo/_data/corpus/manuals/sociedades`

## Changes

- `A` `src/cadrumo/_data/corpus/manuals/sociedades/2022/manifest.json`
- `A` `src/cadrumo/_data/corpus/manuals/sociedades/2022/source.pdf`
- `A` `src/cadrumo/_data/corpus/manuals/sociedades/2022/source.pdf.extracted.json`
- `A` `src/cadrumo/_data/corpus/manuals/sociedades/2022/source.pdf.extracted.md`
- `A` `src/cadrumo/_data/corpus/manuals/sociedades/2022/structure/chapters.json`
- `A` `src/cadrumo/_data/corpus/manuals/sociedades/2022/structure/manual.json`
- `A` `src/cadrumo/_data/corpus/manuals/sociedades/2023/manifest.json`
- `A` `src/cadrumo/_data/corpus/manuals/sociedades/2023/source.pdf`
- `A` `src/cadrumo/_data/corpus/manuals/sociedades/2023/source.pdf.extracted.json`
- `A` `src/cadrumo/_data/corpus/manuals/sociedades/2023/source.pdf.extracted.md`
- `A` `src/cadrumo/_data/corpus/manuals/sociedades/2023/structure/chapters.json`
- `A` `src/cadrumo/_data/corpus/manuals/sociedades/2023/structure/manual.json`
- `A` `src/cadrumo/_data/manual_corpus_text/manuals/sociedades/2022/source.pdf.corpus_text.json`
- `A` `src/cadrumo/_data/manual_corpus_text/manuals/sociedades/2023/source.pdf.corpus_text.json`
- `verify:` `uv run pytest dev/corpus/tests/test_extraction_sidecar_freshness.py::test_manual_pdf_corpus_text_sidecars_exist_and_match_source_sha256 -q` -> `pass`
