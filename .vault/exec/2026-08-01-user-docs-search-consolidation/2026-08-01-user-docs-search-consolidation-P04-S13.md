---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:2eddddf809244d92d67bba21ee33381cb03ac85d08afd05c37a046c60ffb6936'
step_id: 'S13'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Redeploy and live-verify the full-mode index, the casilla destination pages, and the language roots, recording the live checks in the exec record

## Scope

- `dev/deploy/`

## Description

- Ground the deployment and per-root parity contract with `vaultspec-rag` and inspect the current deployment script.
- Attempt the authorized deployment preflight after the source/build work was allowed to proceed.
- Check cloud credentials before mutating any live root; do not fabricate a publish or live verification when authentication is expired.

## Outcome

Deployment was intentionally not performed. The source deployment script is configured for full Pagefind mode and all four language roots, but the local AWS session is expired. The required live publish and post-publish checks therefore remain open.

## Verification

`aws sts get-caller-identity`

`aws: [ERROR]: Your session has expired. Please reauthenticate using 'aws login'.`

No deployment, root mutation, cache invalidation, or live URL claim was made.

## Notes

The strict en/es/ca/hu builds also remain red on the five known sequence/product divergences recorded in P04.S12/P03.S08. Once the user reauthenticates and the source tree reaches the required full-green build boundary, this step can resume without changing the deployment contract.
