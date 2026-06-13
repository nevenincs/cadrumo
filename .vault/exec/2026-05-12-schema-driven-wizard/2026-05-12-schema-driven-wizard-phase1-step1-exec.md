---
tags:
  - '#exec'
  - '#schema-driven-wizard'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
  - "[[2026-05-12-schema-driven-wizard-reference]]"
---

# `schema-driven-wizard` `phase1` `step1`

Landed the `questionary` prompt backend dependency and the wizard
subpackage shell.

## What landed

- `pyproject.toml` gained `questionary>=2.1.1` in the `dependencies`
  table; `uv lock` and `uv sync` resolved the transitive set
  (`prompt-toolkit`, `wcwidth`).
- `src/aeat/application/wizard/__init__.py` is the new subpackage
  marker; the docstring describes the descriptor catalogue contract
  the rest of the package will compose.
- `src/aeat/application/wizard/test_dependency_import.py` smoke-tests
  that the `questionary` distribution is importable, that every
  primitive the runtime will dispatch onto is exposed at top level,
  and that the installed version satisfies the `>= 2.1.1` floor pinned
  by the ADR.

## Gates cleared

- `uv lock` and `uv sync` succeeded.
- `uv run --no-sync pytest src/aeat/application/wizard/test_dependency_import.py`
  is green.
- `uv run --no-sync prek run --files pyproject.toml uv.lock src/aeat/application/wizard/__init__.py src/aeat/application/wizard/test_dependency_import.py`
  passes (ruff check, ruff format, ty type check).

## Not in this Step

- No descriptor model code; that lands next.
- No `questionary` import sites in production code; the prompter
  lands when the runtime is wired.
- No CLI entrypoint changes.
