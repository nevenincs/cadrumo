---
tags:
  - '#research'
  - '#corpus-sidecar-freshness-repair'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:53cc4deef2d836b4bae8b03076ed5d821c78665ce1dc717b0c7ac153c731e0d5'
related: []
---
# `corpus-sidecar-freshness-repair` research: deterministic corpus-sidecar generation and drift detection

The committed corpus contains product-search and evidence derivatives, but HTML and workbook sidecars lack one batch producer/check surface. The current gate reports eight stale normative HTML derivatives and seven missing record-design workbook pairs. Existing PDF text sidecars are current under their separate producer. The ADR must decide whether to add a single enrolled-source generator/check and make it the required operator surface.

## Findings

### HTML and workbook derivatives have writers but no batch owner

`extract_html` writes deterministic sidecar pairs for one normative source, and `extract_workbook` does the same for one record-design workbook. No command enumerates their enrolled source populations, writes the complete set, or performs a no-write expected-output comparison. In contrast, manual PDF text has `extract_manual_corpus_text --check` and matching `just` recipes. `sync_aeat_record_design_corpus` verifies fetched source artefacts and manifests only; it does not create text derivatives. The missing batch owner explains why source changes and new workbooks can land without a corresponding sidecar. `dev/docs/preprocess/normatives_html.py:524`; `dev/docs/preprocess/_workbook.py:257`; `dev/corpus/extract_manual_corpus_text.py:183`; `dev/corpus/sync_aeat_record_design_corpus.py:830`; `justfile:401`.

### The live corpus is presently inconsistent

The freshness run on 2026-09-10 found eight stale normative HTML sidecars and seven record-design workbooks with no sidecar pair. The stale normative files are `orden-eha-3127-2009-art-5.html`, `orden-eha-3290-2008-art-11.html`, `orden-eha-3377-2011-art-5.html`, `orden-hac-1197-2025.html`, `orden-hac-96-2003-tercero.html`, `orden-hac-96-2003.html`, `orden-hap-2783-2015.html`, and `orden-hfp-1338-2023.html`. The missing workbook sources belong to modelos 308, 309, and 353. The product lexical search consumes normative `*.html.extracted.json`, so the first class is a shipped-search correctness defect, not merely developer drift. `dev/corpus/tests/test_extraction_sidecar_freshness.py:172`; `src/cadrumo/application/corpus_search/lexical_index.py:58`.

### Existing gates have partial but not complete coverage

Tree-wide preprocessing gates check committed sidecars for loadability, source-hash freshness, and locality. The corpus gate additionally checks exact HTML producer parity and workbook presence. However, HTML parity skips a source with no sidecar and relies on a comparison floor, so it cannot prove every enrolled normative source has a pair. A common `--check` command should derive the complete expected source set, report missing, stale, mismatched, orphaned, and unexpected multipart derivatives, and be exercised by focused tests. `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py:327`; `dev/corpus/tests/test_extraction_sidecar_freshness.py:172`; `dev/corpus/tests/test_extraction_sidecar_freshness.py:430`.

### The developer RAG hook is complementary, not a substitute

The RAG hook extracts raw corpus HTML and workbooks independently for development indexing. It neither reads nor validates the committed sidecars that product offline search ships. Retaining a permanent parity/freshness boundary is therefore required even after RAG indexing succeeds. `.vaultragpreprocess.toml:1`; `dev/docs/preprocess/hook.py:61`; `.vault/adr/2026-07-13-docs-terminology-search-adr.md`.

### Options for the decision

One option is a one-off regeneration using the existing functions. It fixes today’s artifacts but leaves the missing producer contract intact. A second option is independent HTML and workbook commands; it preserves narrow ownership but duplicates enrollment, check semantics, and recipes. The evidence favors one corpus-sidecar command with type-specific delegation to the current extractors: it has one complete enrolled population, one no-write drift check, and no extractor rewrite. PDF corpus text remains in its existing separate command because it uses a different sidecar schema and runtime reader.

## Sources

- `dev/corpus/tests/test_extraction_sidecar_freshness.py:172`
- `dev/corpus/extract_manual_corpus_text.py:183`
- `dev/corpus/sync_aeat_record_design_corpus.py:830`
- `dev/docs/preprocess/_workbook.py:257`
- `dev/docs/preprocess/hook.py:61`
- `dev/docs/preprocess/normatives_html.py:524`
- `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py:327`
- `justfile:401`
- `src/cadrumo/application/corpus_search/lexical_index.py:58`
- `.vaultragpreprocess.toml:1`
