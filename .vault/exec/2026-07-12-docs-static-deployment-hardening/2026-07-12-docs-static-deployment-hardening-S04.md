---
tags:
  - '#exec'
  - '#docs-static-deployment-hardening'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S04'
related:
  - "[[2026-07-12-docs-static-deployment-hardening-plan]]"
---
# `docs-static-deployment-hardening` `S04` execution

## Description

- Add the governed live delivery contract.

## Outcome

- Require explicit live-test enablement.
- Pass canonical `200`, legacy `308`, missing `404`, and direct S3 `403` checks.
- Require the exact legacy redirect location.

## Notes

- Keep AWS credentials outside normal local tests.
