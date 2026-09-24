---
tags:
  - '#adr'
  - '#website-repository-boundary'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:846239829f9292ae4b378a9418321824dda9e300c48d75dde7ac18ee46164cc3'
related:
  - "[[2026-08-23-website-repository-boundary-adr]]"
  - "[[2026-09-22-website-repository-boundary-docs-deployment-ownership-reference]]"
---

# `website-repository-boundary` adr: `documentation delivery moves to Cloudflare R2 and a Worker` | (**status:** `accepted`)

## Problem Statement

The product documentation was published to a private S3 bucket behind CloudFront, as mapped in `2026-09-22-website-repository-boundary-docs-deployment-ownership-reference`. That route was never armed in CI, its account is not the one the operator's local AWS profile reaches, and the live site had not been republished since 2026-07-12. The operator directed delivery to move to Cloudflare R2, served on both `cadrumo.neve.md/docs/` and `neve.md/cadrumo/docs/`, following the pattern the vaultspec site already uses in the same Cloudflare account.

## Considerations

- The `neve.md` zone, the marketing Pages project and the vaultspec R2-plus-Worker site already live in one Cloudflare account; the docs join that account rather than a separate AWS one.
- `cadrumo.neve.md` is also the marketing landing host, still served by CloudFront; only `/docs*` may change owner.
- Credentials must be isolated from every other site in the account (operator instruction).
- CI runs on a self-hosted fleet whose setup provisions Python tooling but no Node.

## Considered options

- R2 plus one Worker serving immutable release prefixes (chosen): atomic switch and instant rollback by redeploying an earlier release id; same shape as the vaultspec site.
- R2 public bucket with a custom domain: no Worker to maintain, but no 404 semantics, no directory redirects, no release header and a whole-host binding that would take the landing page too.
- Keep S3/CloudFront and arm the missing OIDC role: preserves the existing stack but in an account outside the operator's reach, contrary to the directed migration.

## Constraints

- `cadrumo.neve.md` must be proxied through Cloudflare for a Worker route to apply; CloudFront remains its origin for every other path, which the zone's `full` TLS mode supports.
- Zone redirect rules run before Workers; the two rules that sent `neve.md/cadrumo/docs` to `cadrumo.neve.md` must be disabled for the mirror mount.
- The existing docs-build gates (strict build, cli-sequence goldens, record-bearing search index) stay mandatory before any upload.

## Implementation

- `worker/docs-site.mjs` serves `releases/<RELEASE_ID>/` for both mounts; its unit tests run under Node through `just test-docs-worker`.
- `dev/deploy/r2_objects.py` uploads and lists over R2's S3 API with first-party SigV4 signing; `dev/deploy/cloudflare_api.py` deploys the Worker module through the Cloudflare API, so neither Wrangler nor Node is needed to publish.
- `dev/deploy/docs_static_site.py` composes build, validation, upload, Worker deploy, routes and live verification of both mounts; `provision` performs the one-time zone wiring and `rollback` redeploys an earlier release.
- `.github/workflows/release.yml` publishes from the `docs` environment with five Cloudflare secrets, publishes the registry authority before every docs build, and gains a `docs` phase to republish a ref without a package release.
- The CloudFormation template in `infra/` is retained while CloudFront still serves the landing page.

## Rationale

Immutable release prefixes make every publish reversible without re-uploading, and the release header lets the publisher prove which bytes are live on both mounts. A plain module uploaded through the API keeps CI free of a Node toolchain. Isolated tokens (an R2 key scoped to one bucket, a CI token limited to Worker deploys and routes on `neve.md`) meet the operator's isolation requirement.

## Consequences

- The S3 `docs/` prefix and its CloudFront behaviour stop serving `/docs*` once the zone wiring is applied, but remain in the AWS account; retiring them is a separate, operator-authorised action.
- The landing page now transits Cloudflare's proxy before reaching CloudFront.
- The R2 bucket accumulates one prefix per publish; a retention policy is future work.
