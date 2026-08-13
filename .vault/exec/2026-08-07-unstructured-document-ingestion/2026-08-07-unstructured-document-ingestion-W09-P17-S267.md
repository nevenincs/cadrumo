---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:e40fabcc7020858bf59810623b30dcb22760718ef1a5a1eeba3a92d49156c0d9'
step_id: 'S267'
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
     The S267 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Stop the nif-hash rule matching UTC timestamps, since admitting dot and hyphen separators inside the NIF body makes the Z-suffixed ISO form 12.345678Z a textbook NIF shape - seven digits, separators, trailing letter - so LLMCache.write corrupts created_at to a sha256 prefix and _entry_from_payload then RAISES rather than degrading to a miss, meaning one poisoned entry fails every subsequent read of that partition and repeated reads re-dispatch inference on a machine with no headroom - the plus-00-00 form does not match, so the failure looks intermittent and depends on which serialiser wrote the stamp and ## Scope

- `src/cadrumo/core/redaction/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Stop the nif-hash rule matching UTC timestamps, since admitting dot and hyphen separators inside the NIF body makes the Z-suffixed ISO form 12.345678Z a textbook NIF shape - seven digits, separators, trailing letter - so LLMCache.write corrupts created_at to a sha256 prefix and _entry_from_payload then RAISES rather than degrading to a miss, meaning one poisoned entry fails every subsequent read of that partition and repeated reads re-dispatch inference on a machine with no headroom - the plus-00-00 form does not match, so the failure looks intermittent and depends on which serialiser wrote the stamp

## Scope

- `src/cadrumo/core/redaction/__init__.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Executed. Verified against HEAD: `_ISO_INSTANT_RE`, `_timestamp_spans` and `_outside_timestamps` ship, and the module's own comment restates the collision the row reported — a serialised instant's seconds and microseconds are seven digits with separators and a trailing letter, and `12345678Z` even carries a valid check character.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
