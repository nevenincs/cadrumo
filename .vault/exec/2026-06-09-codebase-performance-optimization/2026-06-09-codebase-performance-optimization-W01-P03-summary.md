---
tags:
  - '#exec'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-06-09'
related:
  - '[[2026-06-09-codebase-performance-optimization-plan]]'
---

# `codebase-performance-optimization` `W01.P03` summary

Completed Phase 3 of Wave 1, optimizing Pydantic model configurations and `TypeAdapter` usage to reduce overhead during justificante parsing.

- Modified: `src/aeat/adapters/inbound/justificante/_extract.py`
- Created: `.vault/exec/2026-06-09-codebase-performance-optimization/2026-06-09-codebase-performance-optimization-W01-P03-S06.md`

## Description

The justificante text-extraction boundary parses and validates the PDF's verification URL. Previously, it constructed a `TypeAdapter(AnyHttpUrl)` instance inline on every verification URL lookup. Since this validation runs in hot loops during batch receipt processing, the instantiation overhead accumulated. We promoted the TypeAdapter to a module-level constant `_ANY_HTTP_URL_ADAPTER`, which is instantiated once when the module loads and reused across all URL validations.

## Tests

- Pytest ran successfully on `src/aeat/adapters/inbound/justificante/tests` with 171 passed tests in 5.63s.
