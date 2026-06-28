---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S78'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# update CLI entrypoint API reference after output-surface enrollment lands

## Scope

- `docs/api/aeat.entrypoints.cli.rst`

## Description

- Verified the entrypoint API reference exists in the generated API tree after output-surface enrollment.
- Compared the plan row path with the current docs tree.
- Ran the docs conformance gate with the `docs` marker enabled.

## Outcome

- The current API reference path is `docs/api/aeat.entrypoints.rst`, which documents `aeat.entrypoints` through `automodule` with members, inheritance, and `ignore-module-all` enabled.
- `uv run pytest -q src/aeat/tests/test_docs_build.py -m docs --tb=short -vv` passed: 1 passed.

## Notes

- The plan row names `docs/api/aeat.entrypoints.cli.rst`, but the current generated API tree has `docs/api/aeat.entrypoints.rst` and `docs/api/aeat.apidocs.cli.rst`; no `docs/api/aeat.entrypoints.cli.rst` file exists.
