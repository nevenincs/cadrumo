---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:e489c7dd56cb7314285b756dd03eeb26dfdde1652ce0db3d3763ef3d1ecf95c3'
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

### 2026-08-07 read-only live-root re-probe

A read-only GET probe of the four public documentation roots returned:

- `https://cadrumo.neve.md/docs/`: HTTP 200.
- `https://cadrumo.neve.md/docs/es/`: HTTP 404.
- `https://cadrumo.neve.md/docs/ca/`: HTTP 404.
- `https://cadrumo.neve.md/docs/hu/`: HTTP 404.

No deployment, cache invalidation, or live mutation was attempted. P04.S12 remains open; the three localized roots are still not proven reachable.

### 2026-08-07 current local parity confirmation

The current shared-tree local integration gate `uv run --no-sync pytest -q -m integration dev/docs/tests/test_deployment_search_parity.py` returned `25 passed in 541.71s`, exercising `en`, `es`, `ca`, and `hu` through the production local Pagefind path. This does not alter the live-root result: `/docs/` returned HTTP 200 while `/docs/es/`, `/docs/ca/`, and `/docs/hu/` returned HTTP 404 on the read-only probe. P04.S12 remains open; no deploy, cache invalidation, or live mutation was attempted.

### 2026-08-07 current all-locale local parity rerun

The authorized real-behaviour integration gate `uv run --no-sync pytest -q -m integration dev/docs/tests/test_deployment_search_parity.py` completed with `25 passed in 383.05s (0:06:23)`, exercising `en`, `es`, `ca`, and `hu` through the production local Pagefind path. This confirms the local full-record projection remains present across all four roots.

The live read-only probe remains unchanged: `/docs/` returned 200, while `/docs/es/`, `/docs/ca/`, and `/docs/hu/` returned 404. AWS STS authentication remains expired, so P04.S12 remains open and no deploy or cache invalidation was attempted.

### 2026-08-11 formal carry-forward

This row stays OPEN by operator decision, and the deferral is recorded rather than absorbed into a green close.

The committed mechanism is present and unchanged: the viewer function maps each language root to its index, the publisher syncs the complete built tree, and the publish path refuses outright when any built language is unreachable from the language entry. What is missing is proof, not code.

The live acceptance property is still unsatisfied: the `es`, `ca` and `hu` roots each return HTTP 404. That evidence is preserved as-is. It cannot be advanced because the AWS session is expired and re-authentication is an operator action; without it the deployed routing and object state cannot be distinguished from the committed mechanism.

Nothing here may be read as a claim that the localized roots respond. The campaign closes with this row open.

### 2026-08-12 the publish would have failed on its own build; two blockers removed

This row stays open on the live proof, but its engineering half moved materially, and what was found changes the value of the pending re-authentication.

The live state was re-verified directly this session rather than inherited from the earlier record. Reading a public site needs no credentials, only publishing does, so the roots were probed over plain HTTPS: the default root answers 200 while `/es/`, `/ca/`, `/hu/`, `/en/` and the casilla destination page all answer 404. The gap is real and current.

More useful: the publish would have failed even with valid credentials. It builds every root through the docs driver under strict settings before it uploads anything, and all three translated builds were red. Two independent causes, both credential-free and both now fixed.

First, the casilla reference generator aborted at builder-inited because `docs.casilla.input_kind.projection_only` and its count sibling had no authored value. A new projection-only input kind had entered the schema, and the surface derives its label keys from that enum precisely so a new member demands its string rather than rendering nothing. The design worked; the strings were simply never written. Authored in all four languages on the register the sibling kinds establish.

Second, five stale preview pages sat in the generated casilla directory from an earlier session, in no toctree, so the nitpicky build warned and failed. Nothing in the tree emits them any more. They are gitignored build residue, not source, and were moved aside rather than deleted outright.

All four roots now build clean: es and ca passed immediately, and hu passed on a sequential re-run after a concurrent registry write raced its cache fingerprint the first time.

So the remaining blocker really is only the credential. Before this session a re-authentication would have hit a failing build; now the publish path is clear up to the upload.

One recurrence risk recorded rather than fixed: the generator does not prune its own output directory, and that directory is gitignored, so stale pages survive across builds and can red the strict build again. A pruning pass belongs with the generator's owner.
