---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-07-17'
body_hash: 'sha256:cd3afba4fb22655b23c3e1c4f444f9619754717404d435b4b7723fa1b0afe63d'
step_id: 'S67'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---

# update error-boundary unwrap tests for shared error redaction behavior

## Scope

- `src/aeat/entrypoints/cli/test_error_boundary_unwrap.py`

## Description

- Validate error-boundary unwrap tests for shared error redaction behavior.

## Outcome

- `uv run pytest -q src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_error_boundary_integration.py src/aeat/entrypoints/cli/test_error_boundary_unwrap.py` passed: 22 passed.

## Notes

- The unwrap tests cover SQLAlchemy-wrapped `AeatError` refusals and genuine unexpected exceptions without suppressing root-cause logging.
