---
tags:
  - '#exec'
  - '#docs-static-deployment'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S06'
related:
  - "[[2026-07-10-docs-static-deployment-plan]]"
---
# `docs-static-deployment` `P03.S06` execution

## Result

- Return 308 from the legacy docs root.
- Return 308 from a legacy docs page.
- Preserve the page query string.
- Return 200 from the canonical docs root.
- Return 404 from a missing canonical page.
- Return 403 from direct S3.

## Verification

- Verify legacy redirect headers.
- Verify canonical CloudFront response.
- Verify private-origin denial.
