---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S05'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Demote vaultspec-rag[mcp] out of [project.dependencies] into the dev dependency group so a published product wheel carries no developer search tooling

## Scope

- `pyproject.toml`

## Description

- Demote `vaultspec-rag[mcp]` from `[project.dependencies]` to the dev dependency group, consolidating the `[mcp]` extra and the `>=0.2.28` pin into the existing dev entry.
- Grep-verify production `src/aeat` carries zero `vaultspec_rag` imports before the demotion.
- Regenerate `uv.lock`.
- Commit `d15b484dfa`.

## Outcome

- A published product wheel no longer carries the developer semantic-search stack; the dev loop keeps it via the dev group.

## Notes

No incidents. No skipped work.
