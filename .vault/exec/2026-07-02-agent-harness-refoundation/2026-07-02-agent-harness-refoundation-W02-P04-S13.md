---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S13'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add guided-workflow prompts that embed the matching skill plus its grounding excerpt

## Scope

- `src/aeat/entrypoints/mcp/_prompts.py`

## Description

- Author `src/aeat/entrypoints/mcp/_prompts.py` as SDK-independent pure
  functions over typed models, mirroring the `_tools`/`_dispatch` split so
  `_server` adapts to SDK types at the boundary (S14, delegated).
- Derive the prompt catalogue from the shipped skills + their validated
  `applies_when` frontmatter — one guided workflow per skill, zero
  registration, no hand-listed surface — plus the `aeat-empezar` orientation
  prompt that embeds the full operator rules.
- Each `prompts/get` payload carries an operating brief (coordinator-authored
  content: follow the embedded playbook, load rules first, never compute a
  figure, confirm the active profile, nothing here submits to AEAT) plus the
  skill document embedded verbatim under its `aeat://skill/{name}` uri.

## Outcome

Authored by the coordinator per the operator directive (prompt content is
skill-adjacent harness content). Smoke-verified: 35 prompts derive (34 skills
+ orientation), `regularizar-atrasos` embeds its 5.6k skill verbatim, the
orientation prompt embeds the 16.8k operator rules, unknown names refuse with
a typed error. Ruff clean. Commit `bb8ced380`, exactly one file. Server
wiring and tests follow as S14/S17 (delegated executor).

## Notes

None.
