---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S102'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S102 - extract config profile bundle commands

Scope: `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/_profile_bundle.py`.

## Description

- Move `config profile export` and `config profile import` into `_config/_profile_bundle.py`.
- Keep the public command paths and payload contracts unchanged.
- Move bundle schema-version validation and profile import/export lifecycle event emission with the bundle commands.
- Keep shared `_atomic_create_profile` in the config root because duplicate and import both use it.

## Outcome

The config root now delegates portable profile bundle import/export to a focused registrar while retaining the shared profile provisioning helper used by duplicate and import flows.

## Notes

The registrar receives profile resolution and atomic-create dependencies from the root, matching the dependency-injection pattern used by the repair-profile extraction.
