---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S07'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W01.P02.S07`

Scope: `src/aeat/application/workflow/test_declaration_key.py`.

## Description

- Converted the workflow declaration-key test import to a relative package import.
- Preserved duplicate-definition and case-folding assertions.
- Verified focused workflow test coverage.

## Outcome

The workflow test no longer contributes to the absolute self-import baseline.

## Notes

No behavior changes were made.
