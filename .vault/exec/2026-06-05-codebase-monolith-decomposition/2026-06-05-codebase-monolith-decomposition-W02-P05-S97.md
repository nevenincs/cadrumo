---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S97'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S97 Config Bucket History Selection

Scope: W02.P05 residual config CLI decomposition.

## Description

- Run RAG search for config bucket history command and event-history filters.
- Run exact discovery over `bucket_history`, `_parse_bucket_event_types`, `_parse_bucket_history_instant`, `_bucket_history_event_matches`, and `_bucket_history_event_payload`.
- Select the bucket-history command group as the next config root extraction slice.

## Outcome

The selected slice is a focused bucket-history registrar: CLI option parsing, filter parsing, event projection, and envelope emission. Event storage and catalogue semantics remain owned by the domain repository.

## Notes

RAG returned the bucket-history command and helper cluster from `_config/__init__.py` with the expected helper boundaries.
