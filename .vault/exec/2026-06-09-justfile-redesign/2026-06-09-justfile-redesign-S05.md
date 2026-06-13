---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S05'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# ignore the relocated workbook_parity directory in pytest options

## Scope

- `pyproject.toml`

## Description

- Updated pytest default configuration in `pyproject.toml` by appending the `--ignore=src/aeat/domain/calculations/registry/tests/workbook_parity` option to the `addopts` setting.

## Outcome

Verification via `pytest --collect-only` on the parent `registry/tests` directory confirms that `workbook_parity` is completely ignored by default during standard test runs (collecting 2212 tests instead of 2230), while directly targeting the file runs it successfully.

## Notes
