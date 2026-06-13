---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S16'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# implement RAG search and index management recipes

## Scope

- `justfile`

## Description

- Implemented `fix-rag` to run vector re-indexing for both code and vault files via `--port 8766`.
- Implemented `audit-rag QUERY` to run on-demand semantic search query delegating to port 8766.
- Implemented `check-rag` to report the local daemon status.
- Implemented `check-semantic` to run programmatic semantic audits.

## Outcome

All RAG queries and index modifications are successfully routed through port 8766 to preserve database lock boundaries.

## Notes
