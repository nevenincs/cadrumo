---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S20'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S20 - residual config apoderado selection

Scope: `src/aeat/entrypoints/cli/_config/__init__.py`, `src/aeat/entrypoints/cli/_config/_google.py`, config CLI tests, and CLI surface tests.

## Description

- Checked `vaultspec-rag` service health before semantic discovery.
- Ran exact discovery over config and google command groups plus related tests.
- Ran semantic discovery for google sync/calc extraction candidates.
- Ran semantic discovery for config auth apoderado command extraction candidates.
- Selected `config auth apoderado` because it is a coherent command subtree with real integration tests, while google calc carries deeper application behavior that should be bounded by backend extraction rather than moved sideways as CLI code.

## Outcome

Selection completed. RAG ranked `apoderado_check`, `apoderado_clear`, `apoderado_status`, `apoderado_configure`, and `apoderado_scopes_list` as coherent extraction candidates.

## Notes

Google `sync calc` remains a high-value future target, but it should be paired with application-layer relocation of calculation sync behavior to respect the no-business-logic-in-CLI directive.
