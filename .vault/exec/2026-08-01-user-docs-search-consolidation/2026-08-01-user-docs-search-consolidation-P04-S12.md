---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:3f4f77f7b52dab5216ac97043a9bce353581cd9946aa9e735307f513d6b95c9a'
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

### 2026-08-06 authorized build/deployment continuation

Strict user-doc builds for en, es, ca, and hu each stop on the same five known sequence/product divergences: profile-setup history ordering, correct-review history expectation, Modelo 100 export authority absence, the Modelo 303 verification-report localized divergence, and the Renta assembly localized-help divergence. No golden was refreshed and no authoritative source was invented.

Deployment was not attempted because `aws sts get-caller-identity` reports an expired session and requires reauthentication. P04.S12 remains open; P04.S13 has no deploy evidence.

### 2026-08-06 current full strict preflight timeout

The current full strict preflight command, `uv run --no-sync python -m dev.docs.build --strict docs/conf.py`, ran for 304.372 seconds and exited with code 124 from the command timeout before returning an actionable build failure or a green result. This is an unverified timeout boundary, not evidence for changing source, refreshing golden artifacts, closing the gate, or publishing deployment. AWS STS authentication remains expired, so the live deployment proof is still unavailable.

### 2026-08-06 current strict build legal-corpus failure

The longer retry of `uv run --no-sync python -m dev.docs.build --strict docs/conf.py` reached Sphinx `builder-inited` and exited with code 1. Registry validation failed before page generation because 39 legal references could not resolve exactly one bundled corpus unit for their declared anchors, including Ley 35/2006 arts. 68.1-68.5, Orden HAC 56/2024 art. 1, Orden HAP 1732/2014 art. 2, Ley 37/1992 and several other Ordenes/RD references. This is an actionable legal-corpus data gate; no resolver fallback, source invention, artifact promotion, or deployment was performed.

### 2026-08-06 current strict build sequence-golden failure

The current strict retry cleared the registry legal-corpus validation after the bounded resolver and sidecar repair. It then reached the sequence-golden gate and exited with code 1 on nine divergences caused by concurrent peer changes (invoice option requirements, category ordering, profile-history ordering, ledger split behavior, and localized registry output). This is not a legal-search failure; the step remains open until a later full build is green.
