---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:95c746a3f96290d4cf14b87e37e7145f2f38b354042ac41ab55df069c4230a73'
step_id: 'S145'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Give the evidence consent CLI module its own tests, since it has none at all and that absence hid two live operator-facing crashes until a lane building on top of it happened to probe a real instance: the survey and the withdrawal verbs both raised on a workflow-state attribute that does not exist, and a re-derivation reader called a signature changed out from under it while being annotated loosely enough that the type checker saw nothing. Drive the real command tree rather than constructing state, since constructing it is what let both defects sit unnoticed

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

## Outcome

## Verification

## Notes
