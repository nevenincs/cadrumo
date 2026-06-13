---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S17'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# implement static quality check and prek runner wrappers

## Scope

- `justfile`

## Description

- Implemented `check-style`, `check-format`, `check-types`, `check-imports`, `check-relative-imports`, `check-dependencies`, and `check-pre-commit` to wrap individual static checkers.
- Implemented `check-all` to aggregate all fast, static checks for developer/CI use.

## Outcome

Verification via `just check-all` runs the aggregated suite cleanly.

## Notes
