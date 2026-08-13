---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:ca4d3f37f289ff12241e17ce383593cb4e07cbd9db65b3c65152df5bde6d3f94'
step_id: 'S290'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S290 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Correct the corpus field mapping for the two totals. The key's grand_total is the computed identity (base 766.30 plus iva 160.92 equals 927.22) while its printed_total is what the page states (890.00), and the draft's grand_total is the PRINTED figure, so the map scores a correct read as wrong on the two divergent documents and declares printed_total unmapped on the false rationale that the draft has no printed-total field. Map printed_total to the draft and rule grand_total unmapped as a computation the reading stage does not perform and ## Scope

- `dev/ingest_harness/_field_mapping.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Correct the corpus field mapping for the two totals. The key's grand_total is the computed identity (base 766.30 plus iva 160.92 equals 927.22) while its printed_total is what the page states (890.00), and the draft's grand_total is the PRINTED figure, so the map scores a correct read as wrong on the two divergent documents and declares printed_total unmapped on the false rationale that the draft has no printed-total field. Map printed_total to the draft and rule grand_total unmapped as a computation the reading stage does not perform

## Scope

- `dev/ingest_harness/_field_mapping.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Executed. Verified against HEAD: the corpus field mapping for the two totals is corrected.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
