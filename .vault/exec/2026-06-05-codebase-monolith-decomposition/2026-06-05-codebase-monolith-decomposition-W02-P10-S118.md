---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S118'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S118 Config Custody Verification

Scope: `W02.P10.S118` verified residual config CLI behavior and the config module size budget after extraction.

## Description

- Run ruff over the config root, custody registrar, custody integration tests, CLI surface tests, apoderado tests, and CLI size guard.
- Run real subprocess custody lifecycle tests through the entrypoint harness.
- Confirm `src/aeat/entrypoints/cli/_config/__init__.py` is 1144 lines and within its frozen budget.

## Outcome

Ruff passed for the touched config and verification files. Pytest collected and passed the config custody, apoderado, and CLI surface tests; the shared size-guard run then failed only on unrelated dirty live CLI WIP: `_app_live.py` is 1178 lines against a 1177-line budget.

## Notes

The live CLI size failure was not swallowed and was not fixed in this commit because doing so would require committing unrelated concurrent `_app_live.py` changes.
