---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S107'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S107 - select modelo CLI test split

Scope: `src/aeat/entrypoints/cli/tests/test_modelo.py src/aeat/entrypoints/cli/tests`.

## Description

- Inspect `test_modelo.py` sections and import dependencies.
- Select the initial registry/discovery surface cluster for extraction.
- Keep filing-record, work-flow, localization, and autocomplete tests in the original module.

## Outcome

Selected a contiguous split covering malformed modelo/period input, describe revision discovery, bindings list/preview, binding read-only guards, evidence-kind parsing, work-unit id validation, and casilla/binding override key validation.

## Notes

The selected cluster is cohesive around registry/discovery and CLI ingress validation, and it removes a large block without changing test behavior.
