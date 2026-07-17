---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S32'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Confirm Modelo 036 and Modelo 037 behavior and metadata remain unaffected by Modelo 145 successor work

## Scope

- `tests/domain/calculations/registry`

## Description

Add a censo-registry regression test that co-loads the new Modelo 145 registry snapshot before asserting Modelo 036 and Modelo 037 contracts.

Verify Modelo 036 still resolves as the active censo work-unit foundation with the committed event-kind vocabulary.

Verify Modelo 037 still resolves only as historical metadata, remains superseded by Modelo 036, and is still absent from active calculation-registry support.

## Outcome

`src/aeat/domain/calculations/registry/tests/test_censo_modelo_foundation.py` now confirms that Modelo 145 registry presence does not alter Modelo 036 active behavior or Modelo 037 historical metadata.

Verification:

- `uv run --no-sync ruff format --check src\aeat\domain\calculations\registry\tests\test_censo_modelo_foundation.py`
- `uv run --no-sync ruff check src\aeat\domain\calculations\registry\tests\test_censo_modelo_foundation.py`
- `uv run --no-sync pytest src\aeat\domain\calculations\registry\tests\test_censo_modelo_foundation.py -q`

## Notes

No blockers. No registry data or censo production behavior changed.
