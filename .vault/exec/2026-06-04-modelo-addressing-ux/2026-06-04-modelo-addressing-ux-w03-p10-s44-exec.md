---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:3c685de92faa2ce4901c92099cf4c7088acbbb417dc462363c32479057222df2'
step_id: 'S44'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P10.S44 work rename addressing

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`

## Description

- Classify `work rename` as natural-key enrolled for active filing workspaces.
- Confirm exact id remains accepted through the shared selector.
- Cover natural-key rename against real persisted work-unit state.

## Outcome

Operators can rename the active visible filing workspace without copying its raw work-unit id.

## Notes

- Adjacent natural-key regression tests passed.
