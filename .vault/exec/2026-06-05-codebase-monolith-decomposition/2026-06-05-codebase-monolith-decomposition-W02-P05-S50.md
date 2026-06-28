---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S50'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S50 - select residual config auth command group

Scope: `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/tests`.

## Description

- Inspect remaining `aeat config` command groups and callable lengths.
- Identify profile, repair, bucket, auth, reset, and status surfaces still in the root module.
- Select the auth subgroup as the next extraction target.

## Outcome

The `aeat config auth` subgroup was selected because it is a coherent authentication surface, large enough to materially reduce `_config/__init__.py`, and already has focused auth behavior and output-language tests.

## Notes

The resident RAG search for this slice timed out; exact command and callable discovery provided enough selection evidence.
