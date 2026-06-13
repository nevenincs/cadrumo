---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S18'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# update CI workflow step names and just commands

## Scope

- `.github/workflows/ci.yml`

## Description

- Updated CI workflow step executions to target the redesigned just recipe taxonomy:
  - Lint runs `just check-style` and `just check-relative-imports`.
  - Typecheck runs `just check-types`.
  - Hooks runs `just check-pre-commit`.
- Purged transient epic terminology ("Wave 1") from comments.

## Outcome

CI workflow steps align with the redesigned prefix-standardized build harness.

## Notes
