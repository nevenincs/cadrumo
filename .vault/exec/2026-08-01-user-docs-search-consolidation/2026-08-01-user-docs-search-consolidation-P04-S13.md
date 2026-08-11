---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:9e67587283dce75dd02bbf29f8bb5e70e5a0fd508c786944dd42baeccb166b44'
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

### 2026-08-06 current full strict preflight timeout

The current full strict preflight command, `uv run --no-sync python -m dev.docs.build --strict docs/conf.py`, ran for 304.372 seconds and exited with code 124 from the command timeout before returning an actionable build failure or a green result. This is an unverified timeout boundary, not evidence for changing source, refreshing golden artifacts, closing the gate, or publishing deployment. AWS STS authentication remains expired, so the live deployment proof is still unavailable.

### 2026-08-06 current strict build legal-corpus failure

The longer retry of `uv run --no-sync python -m dev.docs.build --strict docs/conf.py` reached Sphinx `builder-inited` and exited with code 1. Registry validation failed before page generation because 39 legal references could not resolve exactly one bundled corpus unit for their declared anchors, including Ley 35/2006 arts. 68.1-68.5, Orden HAC 56/2024 art. 1, Orden HAP 1732/2014 art. 2, Ley 37/1992 and several other Ordenes/RD references. This is an actionable legal-corpus data gate; no resolver fallback, source invention, artifact promotion, or deployment was performed.

### 2026-08-06 current strict build sequence-golden failure

The current strict retry cleared the registry legal-corpus validation after the bounded resolver and sidecar repair. It then reached the sequence-golden gate and exited with code 1 on nine divergences caused by concurrent peer changes (invoice option requirements, category ordering, profile-history ordering, ledger split behavior, and localized registry output). This is not a legal-search failure; the step remains open until a later full build is green.

### 2026-08-11 formal carry-forward

This row stays OPEN by operator decision. No deployment was performed, no root was mutated, no cache was invalidated, and no live URL claim is made.

The source deployment configuration is ready: full Pagefind mode is pinned for every root and all four language roots are configured. The blocker is solely that the AWS session is expired, so the publish and its post-publish checks cannot run.

Three checks remain unproven and are named here so the close cannot imply them: that every deployed root's entry carries the injected record corpus in that root's language, that the casilla destination page resolves live, and that the `es`, `ca` and `hu` roots respond.
