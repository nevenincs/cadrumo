---
tags:
  - '#exec'
  - '#just-tooling-bootstrap'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S01'
related:
  - '[[2026-06-04-just-tooling-bootstrap-plan]]'
---

# S01 Declare Missing Audit Dependencies

Scope: `pyproject.toml`, `uv.lock`.

## Description

- Add configured dead-code and dependency-audit tools to the development dependency group.
- Regenerate the lockfile through the project `uv` workflow.
- Keep duplication analysis outside the Python lock by using a pinned `npx` invocation in the `just` recipe.

## Outcome

`deptry` and `vulture` are declared for the local development environment, and the lockfile resolves with those tools and their required transitive dependencies.

## Notes

An initial dependency add attempt was blocked by locked local virtual-environment entrypoints. The manifest change and lockfile regeneration were completed without relying on stash, reset, checkout, or destructive git operations.
