---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:359341d2a2e83e6854cfbc137f425cafeaf5de9bc8af9a911ae378ab06197ea9'
step_id: 'S113'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Give the provenance stamp a canonical constructor beside its parser, since five producers hand-format the string and the grammar of transport then reader is written down in only one of the six places. One of the five does not follow it at all and misparses its reader name as its transport, which was confirmed by probe rather than reasoned, and that producer is the one reader besides the extractors that accepts a provider, so a cloud read there is today indistinguishable from a local one. Two others hardcode a local transport which is truthful only because their requests pin the local provider literally, the same latency the text extractor carried before it bit. The gate is the part that matters more than the constructor: assert every producer routes through it, because without that a sixth producer simply hand-formats a sixth string

## Scope

- `src/cadrumo/llm`
- `src/cadrumo/application/ledger`

## Description

## Outcome

Executed. Verified against HEAD by its own gate: `test_no_production_module_hand_formats_a_provenance_stamp` ships, which is precisely the singularity the row asked for.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
