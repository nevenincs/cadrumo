---
tags:
  - '#exec'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S06'
related:
  - "[[2026-06-09-codebase-performance-optimization-plan]]"
---




# Reuse TypeAdapter(AnyHttpUrl) instance in _extract.py instead of creating it inline

## Scope

- `src/aeat/adapters/inbound/justificante/_extract.py`

## Description

- Replaced inline `TypeAdapter(AnyHttpUrl)` instantiation in `_extract_verification_url` with a module-level constant `_ANY_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)` to avoid instantiation overhead in hot loops.

## Outcome

- Done. The TypeAdapter instance is instantiated once when the module loads, speeding up receipt parsing.

## Notes

