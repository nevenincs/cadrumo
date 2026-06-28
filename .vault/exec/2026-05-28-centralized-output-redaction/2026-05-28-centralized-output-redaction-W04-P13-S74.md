---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S74'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# update redaction API reference after central policy consolidation

## Scope

- `docs/api/aeat.core.redaction.rst`

## Description

- Verified the redaction API reference stub remains present for the consolidated central redaction package.
- Confirmed the stub delegates to autodoc instead of copying public signatures into handwritten prose.
- Ran the docs conformance gate with the `docs` marker enabled.

## Outcome

- `docs/api/aeat.core.redaction.rst` documents `aeat.core.redaction` through `automodule` with members, inheritance, and `ignore-module-all` enabled.
- `uv run pytest -q src/aeat/tests/test_docs_build.py -m docs --tb=short -vv` passed: 1 passed.

## Notes

- No source or API-reference content change was required for this closeout step.
