---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:efca850a12d5fc5055e61004de2a1cb677d8b341ec5f13f4aceb9efb8bf74c90'
step_id: 'S86'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Move the manager pilot behind the TUI devtools facade or installed out-of-process boundary

## Scope

- `src/cadrumo/tests/manager_pilot.py`

## Description

- Remove the retired shared-test manager-pilot home and import every consumer directly from the canonical TUI test defining module.
- Enforce one `wait_until_settled` definition and exactly seven direct consumers with a repository-wide AST census over product, development, and packaging sources.
- Reject package-facade, alias-based, private, and constant dynamic-import reaches, including full `from module import alias` targets.

## Outcome

The manager-pilot helper has one canonical defining module under the TUI test package. The retired home is absent, the package initializer is inert, and no shim or re-export remains. Ruff passed and the exact integration gate passed; an independent architecture review approved the hardened global proof.

## Notes

The plan row's facade alternative was deliberately not used: the project-wide no-facade rule requires direct imports from the defining module.
