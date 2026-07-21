---
tags:
  - '#exec'
  - '#docs-static-deployment-hardening'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S01'
related:
  - "[[2026-07-12-docs-static-deployment-hardening-plan]]"
---
# `docs-static-deployment-hardening` `S01` execution

## Description

- Add post-invalidation endpoint checks.
- Require the canonical legacy redirect location.
- Refuse CI and GitHub Actions publishing.

## Outcome

- Confirm canonical `200`, legacy `308`, missing `404`, and direct S3 `403`.
- Confirm the live legacy destination.
- Confirm CI refusal before AWS access.

## Notes

- Require fresh AWS authentication before any publish.
