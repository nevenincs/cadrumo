---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S25'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Emit the plugin agents/ tree mapping persona frontmatter to Claude-native fields (tools/disallowedTools), never the non-Claude mode: field

## Scope

- `src/aeat/agent/_workspace.py`

## Description

- Extend `_workspace.py` to emit the plugin `agents/` tree, mapping each persona's authored frontmatter to Claude-native fields: `name` from the persona slug, `description` from the persona's first prose paragraph.
- Give the coordinator persona — the sole read-only-scoped persona — an explicit `disallowedTools` list of `[Edit, Write, NotebookEdit]`.
- Leave every mutating persona's tool access to the existing server-side persona gate rather than a client-side `disallowedTools` list.
- Emit zero non-Claude `mode:` fields in the generated agent frontmatter.
- Landed together with `S26` and `S27` in one commit because the three facets (agents tree, `.mcp.json`, `userConfig` persona option) co-build one emission function in one file, and the plan lists them as sequential same-file Steps.
- Commit `ccb13180be`.

## Outcome

- Every generated agent `.md` carries Claude-native `tools`/`disallowedTools` frontmatter, never `mode:`.

## Notes

No incidents. No skipped work.
