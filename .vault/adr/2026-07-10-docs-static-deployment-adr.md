---
tags:
  - '#adr'
  - '#docs-static-deployment'
date: '2026-07-10'
modified: '2026-07-10'
related:
  - "[[2026-07-10-docs-static-deployment-research]]"
---
# `docs-static-deployment` adr: `Cadrumo docs delivery` | (**status:** `accepted`)

## Problem Statement

Publish one docs site at both required URLs.

## Considerations

- Keep storage private.
- Keep one canonical URL.
- Limit deployment access.
- Preserve missing-page `404` responses.

## Considered options

- Reject public S3 website hosting because objects become public.
- Reject duplicate Cloudflare sites because delivery would split.
- Reject GitHub deployment because release policy forbids publishing workflows.
- Accept private S3, CloudFront, and one Cloudflare redirect.

## Constraints

- AWS, DNS, IaC, and deployment access do not exist yet.
- Deploy only full strict builds with Pagefind output.
- Exclude `.doctrees` from uploads.
- Keep deployment human-gated and local.

## Implementation

- Serve `https://cadrumo.neve.md/docs/` from CloudFront.
- Keep S3 private behind CloudFront OAC.
- Rewrite docs paths and directory indexes with a CloudFront Function.
- Redirect `https://neve.md/cadrumo/docs/...` in Cloudflare.
- Keep unrelated `neve.md` paths unchanged.
- Deploy through a local AWS-authenticated script.

## Rationale

Use one private origin and one canonical URL.

## Consequences

- Add AWS and Cloudflare setup work.
- Avoid duplicate content and public bucket access.
- Require CloudFront invalidation after each deploy.
- Keep deployment manual until policy changes.
