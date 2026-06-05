---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S144'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S144 Profile Censo Registrar Split

Scope: `src/aeat/entrypoints/cli/_config/_profile_censo.py`; `src/aeat/entrypoints/cli/_config/tests`.

## Description

- Split profile censo command registration into focused `refresh`, `show`, `compare`, and `apply` helper registrations.
- Keep the public `profile censo` Typer subgroup and command payloads unchanged.

## Outcome

- `register` now only builds the subgroup, delegates command attachment, and mounts the subgroup.
- Verified by `ruff check` and config/profile CLI lifecycle tests.

## Notes

- No censo comparison or application policy was moved into the entrypoint layer.
