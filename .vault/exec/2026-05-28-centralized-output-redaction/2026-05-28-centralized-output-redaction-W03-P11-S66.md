---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S66'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# update error-boundary integration tests for shared error redaction behavior

## Scope

- `src/aeat/entrypoints/cli/test_error_boundary_integration.py`

## Description

- Validate error-boundary integration tests for shared refusal redaction behavior.

## Outcome

- `uv run pytest -q src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_error_boundary_integration.py src/aeat/entrypoints/cli/test_error_boundary_unwrap.py` passed: 22 passed.

## Notes

- The focused batch exercises real CLI error-boundary behavior and keeps traceback/output redaction assertions on the operator-visible surface.
