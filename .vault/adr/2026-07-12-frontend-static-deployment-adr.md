---
tags:
  - '#adr'
  - '#frontend-static-deployment'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-07-12-frontend-static-deployment-research]]"
---
# `frontend-static-deployment` adr: `Cadrumo frontend delivery` | (**status:** `accepted`)

## Problem Statement

- Publish the current Cadrumo frontend at the canonical site root.

## Considerations

- Reuse the live private S3 and CloudFront stack.
- Preserve public `/docs/*` content.
- Keep deployment local and human-gated.
- Test before publishing dirty frontend source.

## Considered options

- Reject a second bucket and distribution because one host already has one private origin.
- Reject public S3 website hosting because it exposes objects.
- Reject CI publishing because release policy requires a local human gate.
- Accept root publishing to the shared private origin.

## Constraints

- Publish only `frontend/dist`.
- Exclude `docs/*` from root synchronisation and deletion.
- Require literal `publish-cadrumo-frontend` confirmation.
- Refuse publishing when CI markers exist.
- Add and pass publisher tests before the first frontend publish.
- Require a successful frontend build before synchronisation.

## Implementation

- Build local `frontend/` source.
- Validate required root artifacts.
- Sync the build to the bucket root.
- Preserve `docs/*`.
- Invalidate root and asset paths.
- Require root `200`, root missing `404`, docs `200`, and direct S3 `403`.

## Rationale

- Reuse proven private delivery without risking documentation.

## Consequences

- Publish current local frontend source only after tests pass and a human confirms.
- Keep one CloudFront alias and one cache boundary.
- Require CloudFront invalidation after each publish.
