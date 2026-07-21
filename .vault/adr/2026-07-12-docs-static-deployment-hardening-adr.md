---
tags:
  - '#adr'
  - '#docs-static-deployment-hardening'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-07-11-docs-static-deployment-hardening-research]]"
---
# `docs-static-deployment-hardening` adr: `Cadrumo delivery safeguards` | (**status:** `accepted`)

## Problem Statement

- Close post-deployment verification and release-control gaps.

## Considerations

- Preserve private, canonical, human-gated delivery.
- Verify delivery after CloudFront invalidation.
- Keep release recovery available.

## Considered options

- Reject unverified publishing because public failures remain undetected.
- Reject CI publishing because automation bypasses the human gate.
- Defer immutable release switching because direct sync remains current.
- Accept endpoint checks and CI refusal.

## Constraints

- Keep deployment local and AWS-authenticated.
- Keep canonical URL and legacy redirect unchanged.
- Keep private S3 origin inaccessible.
- Keep strict build, sitemap, and Pagefind validation.

## Implementation

- Check canonical `200` after invalidation.
- Check legacy redirect `308` after invalidation.
- Check missing-page `404` after invalidation.
- Check direct S3 `403` after invalidation.
- Refuse publish when `CI` or `GITHUB_ACTIONS` is set.
- Defer immutable release staging and origin switching.

## Rationale

- Detect public delivery failure before reporting success.
- Preserve explicit human release authority.
- Avoid premature release-architecture expansion.

## Consequences

- Fail publishing when endpoint checks fail.
- Require local operator credentials for publishing.
- Retain direct-sync partial-release risk.
- Revisit immutable releases before automated publishing.
