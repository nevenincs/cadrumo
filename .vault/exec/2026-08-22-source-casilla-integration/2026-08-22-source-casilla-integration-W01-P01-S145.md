---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:7cc6977a76600eb7c18814c19a378ccdbac65bf5a7506247a4ef3fd72afb3178'
step_id: 'S145'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# persist resolver identity through calculation source provenance and encrypted revision round trips

## Scope

- `src/cadrumo`

## Description

- Require exact resolver identity on application provenance and persisted domain source references.
- Stamp every production source resolver and refuse resolution/provenance identity mismatch.
- Preserve resolver identity through modelo projection, encrypted catalogue persistence, audit digest, and CLI payloads.
- Join connectivity authority verification to resolver, binding source, source reference, and fingerprint.
- Refuse legacy encrypted rows without resolver identity and prove wrong-resolver mutations fail closed.
- Publish the canonical manual-input resolver identity from the production route declaration.

## Outcome

Every persisted source-provenance row now identifies the exact resolver that produced it. The required field has no compatibility default, survives real encrypted save/load and operator projection, contributes to the source-provenance trace digest, and is part of the connectivity authority's relational match. Existing calculation revision content addressing remains unchanged because source provenance is an additive audit trace rather than an identity input; tests explicitly pin that boundary.

## Notes

Collection completed before the schema edit. The feature-surface test gate passed with 139 selected tests and 28 integration-marked tests deselected by repository policy. The known whole-tree import-hygiene scan baseline remains the unrelated legacy TUI disposition for `_recovery_words_screen`; no new private cross-package imports were introduced.
