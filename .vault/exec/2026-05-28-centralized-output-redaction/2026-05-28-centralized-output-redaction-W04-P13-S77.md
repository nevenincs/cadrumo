---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S77'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# update JSON-contract API reference after envelope redaction lands

## Scope

- `docs/api/aeat.core.json_contract.rst`

## Description

- Verified the JSON-contract API reference stub remains present after envelope redaction was enrolled.
- Confirmed the generated-reference surface is sourced from module docstrings through autodoc.
- Ran the docs conformance gate with the `docs` marker enabled.

## Outcome

- `docs/api/aeat.core.json_contract.rst` documents `aeat.core.json_contract` through `automodule` with members, inheritance, and `ignore-module-all` enabled.
- `uv run pytest -q src/aeat/tests/test_docs_build.py -m docs --tb=short -vv` passed: 1 passed.

## Notes

- No source or API-reference content change was required for this closeout step.
