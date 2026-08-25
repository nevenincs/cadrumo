---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:eda3d2aef2ef9e3243677fda613d26a68028852f0fbffe3e4ad0349b32ca2563'
step_id: 'S20'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Atomically regenerate and validate the five explicit Modelo 303 export trees

## Scope

- `dev/registry/pipeline/_tree_validation.py`
- `dev/registry/tests/test_generated_export_trees.py`
- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`

## Description

- Adjudicate normalized loader semantics for every epoch before publication.
- Preserve minimal source-backed sibling revision metadata solely as a strict-continuity witness during one-target validation.
- Prove the 2026 target succeeds with declared predecessor metadata and refuses absent, missing, or mismatched witnesses.
- Stage the canonical annual-Orden support authority in isolated M303 generation tests.
- Publish all five epochs through the canonical atomic publisher and rerun independent check mode.

## Outcome

Commits `411580714b` and `434502d5d9` resolve the generic target-only continuity validation gap and regenerate exactly 35 canonical export/provenance files across the five M303 epochs. The only semantic changes beyond provenance are canonical revision-derived layout identities for the two 2024 epochs and 2026; no reviewed map or profile was rewritten. Clean detached verification passed the continuity mutation case, all five M303 target checks, fifteen generated-tree checks, and sixteen publication tests.

## Notes

The generic validator still validates exactly one generated target; sibling data is a continuity-only witness and never a second candidate or full-root fallback. A broad unrelated M130 fixture remains red on a stale source hash. Current shared-tree collection is independently blocked by a peer user-profile relocation, so final proof is from the clean detached candidate.
