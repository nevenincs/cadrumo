---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `Wave 3` `Modelo 115 filing boundary hardening`

Hardened the Modelo 115 application filing boundary with real registry-backed
draft and approval tests.

- Modified: `src/aeat/application/filing/test_filing.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

This step adds application-layer behaviour coverage for Modelo 115 without
defining a local casilla schema, local formula set, or fallback fixture.
The tests build a draft through `build_runtime_schema_provider`, `build_draft`,
and the committed `registry/aeat/modelos/115.toml` definition, then approve the
same draft through `approve_draft`.

The build test verifies that computed casillas 03 and 05 are produced by the
registry calculation path, that the values match the committed official
withholding formula, and that the draft carries the registry schema version.
The approval test verifies that review/approval fingerprinting includes the
Modelo 115 registry schema surface.

This does not close the Modelo 115 live sanitized fixture row. The previous
read-only declaration-register scan found no Modelo 115 filed rows for the
authenticated account and scanned years, so there is no live submitted-file or
declaration-copy artefact to sanitize in this step.

## Tests

- `uv run ruff check src\aeat\application\filing\test_filing.py`
- `uv run ty check src\aeat\application\filing\test_filing.py`
- `uv run pytest src\aeat\application\filing\test_filing.py -q`
