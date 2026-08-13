---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:ab9ee4d8ba61345d12cf66058c95dda049765c8560adf4d8087c389b73f2e36e'
step_id: 'S267'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Stop the nif-hash rule matching UTC timestamps, since admitting dot and hyphen separators inside the NIF body makes the Z-suffixed ISO form 12.345678Z a textbook NIF shape - seven digits, separators, trailing letter - so LLMCache.write corrupts created_at to a sha256 prefix and _entry_from_payload then RAISES rather than degrading to a miss, meaning one poisoned entry fails every subsequent read of that partition and repeated reads re-dispatch inference on a machine with no headroom - the plus-00-00 form does not match, so the failure looks intermittent and depends on which serialiser wrote the stamp

## Scope

- `src/cadrumo/core/redaction/__init__.py`

## Description

## Outcome

Executed. Verified against HEAD: `_ISO_INSTANT_RE`, `_timestamp_spans` and `_outside_timestamps` ship, and the module's own comment restates the collision the row reported — a serialised instant's seconds and microseconds are seven digits with separators and a trailing letter, and `12345678Z` even carries a valid check character.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
