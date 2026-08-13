---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:534385b15c9cbebf857228a3afa2b8f0905f4a79b70ac095c887a8c0e1c32325'
step_id: 'S269'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Rule whether a near-miss of a valid Spanish identity should redact, since a mistyped ES identity survives the funnel raw and discloses 10 of its 11 characters while a mistyped identity of any shape-only member state redacts - measured ESB12345675 and ESB99999999 raw against DE811234568 and DE811234500 redacted - and this application reading paths PRODUCE mistyped identities because detecting them is what the anchoring apparatus exists for, so the population most likely to carry a transcription error is the one whose errors leak - inherited from SHA256_PREFIX_IF_IDENTITY rather than introduced, so the ruling covers the strategy not one arm

## Scope

- `src/cadrumo/core/redaction/__init__.py`

## Description

## Outcome

Executed. Verified against HEAD: the ruling is taken at strategy level as the row required. The personal identity is split into two rules by whether a separator breaks the span — the unbroken arm hashes a lookalike rather than risk missing a mistyped identity, and the separator-bearing arm was carved out on measurement.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
