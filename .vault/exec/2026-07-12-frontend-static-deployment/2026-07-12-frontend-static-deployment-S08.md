---
tags:
  - '#exec'
  - '#frontend-static-deployment'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S08'
related:
  - "[[2026-07-12-frontend-static-deployment-plan]]"
---
# `frontend-static-deployment` `S08` execution

## Description

- Add the root synchronisation dry run.

## Outcome

- Use the exact publish sync with `--dryrun`.
- Fail if docs mutations are planned.

## Notes

- Do not upload or invalidate during dry run.
