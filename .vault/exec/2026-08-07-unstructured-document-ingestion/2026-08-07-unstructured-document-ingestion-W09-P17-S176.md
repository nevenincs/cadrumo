---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:c0000459293eb52e3506bc75fbaf97abe6c7955e429c631f64c26a1e25437e47'
step_id: 'S176'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Re-couple the explicit anchor to its value, since the anchor parameter removed the relation that made a textual grounding sound. A textual field grounds on the anchor alone by design, which was correct while the anchor defaulted to the value because anchor-found implied value-present, and the new parameter breaks that: a value of ZW with an anchor of ESP against a record stating ESP grounds ANCHORED, so the envelope asserts the document evidences ZW and nothing in the module can refuse it. The docstring presents the reuse as inheriting the decimal relation guarantee, but that one is VERIFIED by a parse resolving contradicted when it disagrees while the country correspondence is verified by nothing, so they are the same shape and not the same guarantee. Give the derived path its parse through an optional derivation callable resolving contradicted when the derivation of the anchor differs from the value, or refuse an explicit anchor for a string value unless a derivation is supplied, and correct the docstring to state which leg is checked

## Scope

- `src/cadrumo/application/ledger`

## Description

## Outcome

Executed. Verified against HEAD, on BOTH limbs the row offered as alternatives: `_evaluate_anchor_against` takes a `derive` callable and resolves CONTRADICTED when the re-derivation disagrees with the value, AND the structured path raises when a caller supplies an explicit anchor for a textual value with no derivation, naming the exact hazard the row described.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
