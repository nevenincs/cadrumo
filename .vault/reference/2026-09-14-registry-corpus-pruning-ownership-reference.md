---
tags:
  - '#reference'
  - '#registry-corpus-pruning'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:56f36044334cd830ed9efb3a595fbaac50a555fab97c8cf5b58f5488febebb01'
related: []
---
# `registry-corpus-pruning` reference: `ownership`

## Summary

The registry source tree is concurrently undergoing authority publication changes; those edits are outside this cleanup. Corpus pruning follows exact-path consumer tracing and byte or typed-payload comparison, not filename age.

`dev/registry/compiler/record_design_sources.py:246` loads correction annotations beside the exact source binary. Two Modelo 100 XLSX annotations target absent binaries; retained XLS annotations carry the same correction instructions. `dev/corpus/sync_aeat_record_design_corpus.py` now enrolls correction paths as semantic annotations in the existing artifact catalogue, which reports orphaned targets.

The Modelo 720 instruction PDF duplicated the canonical record-design PDF byte for byte (SHA256 ac324b935b690f0b6fe12dc8351c324cc804170750f483b0768d6417dd4976b7). Its Markdown extraction is byte-identical, extracted JSON units are equal, and normalized runtime text is equal. The canonical source is already pinned by `registry/aeat/legal/foreign-assets.toml`. Remove the duplicate PDF and its three derivatives together, retaining the procedure page and updating provenance and source comments.

Retain historical Modelo 037 retirement evidence, annually addressed manual chapter structures, GROI parser fixtures, the formula-bearing Modelo 200 XLSX, and curated Renta evidence overlays: each still has a consumer. The latter two need provenance or representation work, not deletion. XML responses stored under HTML names need parser-aware normalization before changing cited source paths.

Validation belongs to record-design corpus support, corpus provenance, extraction freshness, and affected record-design parser tests. This is not a proof that every old-looking repository file is removable.
