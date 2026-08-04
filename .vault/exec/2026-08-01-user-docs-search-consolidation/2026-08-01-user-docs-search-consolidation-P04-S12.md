---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:237cca9c461f78db39a06ebdaa287217cf6a97b84591e2315e98703792df63ec'
step_id: 'S12'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Close the gap that leaves the built language roots unreachable on the live site and prove es, ca, and hu roots respond after deploy

## Scope

- `dev/deploy/docs_static_site.py`

## Description

- Run focused vaultspec-rag discovery over the deployment surface and read the accepted plan, ADR deployment ruling, and existing P04 execution records.
- Inspect the committed CloudFront router and publisher sync path for the localized-root delivery mechanism.
- Probe the live Spanish, Catalan, and Hungarian documentation roots and their expected public paths.
- Check the local AWS CLI session boundary without changing cloud state.

## Outcome

P04.S12 remains open. The repository already contains the intended local mechanism: the CloudFront viewer function maps each language root to its index and the publisher syncs the complete built tree beneath the `docs/` prefix. The live acceptance property is not satisfied: the `es`, `ca`, and `hu` roots each returned HTTP 404.

## Notes

No implementation files changed. The AWS CLI is installed, but `aws sts get-caller-identity` reports that the session has expired and the worker's CloudFormation inspection could not complete. The deployed routing/object state therefore cannot be distinguished from the committed mechanism without re-authentication. Do not close this step or dispatch the redeploy/live-verification step until an authenticated operator session proves the roots respond.
