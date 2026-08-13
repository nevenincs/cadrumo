---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:46eda120682c25d23592d5a6b854dfd08f76b704df369050c9ab4a94ae5800fb'
step_id: 'S177'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Search the record text nodes rather than its serialization when grounding a structured value, since the whole decoded record including tag names is passed as the haystack and the boundary rule applies only at numeric edges, so a two-character code matches inside markup: a UBL document carrying NO country element grounds one, because ID for Indonesia matches inside the ID element tag. The docstring claims the check catches a reader pointing at an element the document does not carry and for this field class it does not, and several alpha-2 codes are ordinary substrings of the markup vocabularies. Predates the widening but the widening introduced the first field whose values are two characters, which is where the collision becomes realistic. Narrowing the haystack weakens no existing case since every other structured field is read from a text node too

## Scope

- `src/cadrumo/application/ledger`

## Description

## Outcome

Executed. Verified against HEAD: text-node grounding is present in the parser and the draft rather than searching the record's serialization.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
