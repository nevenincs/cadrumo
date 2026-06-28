---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S64'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# update registry corpus tests to prove non-sensitive rows remain unredacted

## Scope

- `src/aeat/entrypoints/cli/test_registry_corpus.py`

## Description

- Validate registry corpus CLI tests to confirm non-sensitive registry rows still render without accidental over-redaction.

## Outcome

- `uv run pytest -q src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_error_boundary_integration.py src/aeat/entrypoints/cli/test_error_boundary_unwrap.py` passed: 22 passed.

## Notes

- The registry corpus check was run with adjacent error-boundary tests because S64-S67 share the centralized error/output rendering boundary.
