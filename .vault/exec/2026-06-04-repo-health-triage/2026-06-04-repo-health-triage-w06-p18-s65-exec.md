---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S65'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W06.P18.S65`

Scope: `src/aeat/adapters/inbound/declaracion/test_exception_hygiene.py`.

## Description

- Narrowed `_location` line-number access through `getattr`.
- Added an integer assertion so the test helper still fails if a non-located AST
  node is passed.

## Outcome

The S65 exception-hygiene AST narrowing bucket is closed. Ty no longer reports
the `ast.AST.lineno` diagnostic, and the exception-hygiene inventory tests still
pass.

## Notes

Verification:

- `uv run --no-sync ty check src/aeat/adapters/inbound/declaracion/test_exception_hygiene.py --output-format concise`
- `uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/test_exception_hygiene.py -q`
