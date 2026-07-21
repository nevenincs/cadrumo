---
tags:
  - '#exec'
  - '#docs-static-deployment'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S03'
related:
  - "[[2026-07-10-docs-static-deployment-plan]]"
---
# Build, validate, upload, and invalidate docs

## Scope

- `dev/deploy/docs_static_site.py`

## Description

- Add the human-gated deployment command.
- Bind uploads to stack outputs.
- Require canonical Pagefind builds.

## Outcome

Syntax and review checks pass.

## Notes

The stack must exist before deployment.
