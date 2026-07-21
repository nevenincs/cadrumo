---
tags:
  - '#exec'
  - '#docs-static-deployment'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S01'
related:
  - "[[2026-07-10-docs-static-deployment-plan]]"
---
# Define the private S3 and CloudFront stack

## Scope

- `infra/docs-static-site.yaml`

## Description

- Add the private S3 and CloudFront stack.
- Request the ACM certificate.
- Reject dotted bucket names.

## Outcome

Template validation passes.

Certificate validation is pending Cloudflare DNS.

## Notes

Cloudflare API access is not configured.
