---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W01.P001'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---



# `cli-workflow-redesign` `W01.P001`

Completed the backend implementation phase for the apex root and lifecycle
contract.

- Created: `src/aeat/application/operator_surface/__init__.py`
- Created: `src/aeat/application/operator_surface/_contract.py`
- Created: `src/aeat/application/operator_surface/_errors.py`
- Created: `src/aeat/application/operator_surface/_models.py`
- Created: `src/aeat/application/operator_surface/test_contract.py`
- Modified: `src/aeat/core/errors/registry/_application.py`
- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

Added `aeat.application.operator_surface` as the non-CLI owner for the apex
operator surface contract. The package defines strict Pydantic models for the
accepted roots, retired root suggestions, modelo lifecycle vocabulary,
source-kind taxonomy and parser aliases, service ownership, stable log fields,
and registered application error codes.

The contract keeps runtime behavior out of `src/aeat/entrypoints/cli`.
It exposes immutable backend data and service functions that later CLI adapters
can call without duplicating business rules, validation policy, lifecycle
ordering, source-kind vocabulary, logging metadata, or error taxonomy.

The application error registry now includes
`REFUSED_OPERATOR_SURFACE_CONTRACT` for rejected surface requests. The contract
uses `aeat.core.logging.get_logger` and emits only non-secret log metadata.

Closed plan rows: `W01.P001.S0001`, `W01.P001.S0002`,
`W01.P001.S0003`, `W01.P001.S0004`, `W01.P001.S0005`,
`W01.P001.S0006`.

## Tests

`uv run --no-sync pytest src/aeat/application/operator_surface/test_contract.py -q`

`uv run --no-sync ruff check src/aeat/application/operator_surface src/aeat/core/errors/registry/_application.py`

`uv run --no-sync python -m compileall -q src/aeat/application/operator_surface src/aeat/core/errors/registry/_application.py`

`uv run --no-sync vaultspec-core vault plan status .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md --json`

`pyright` and `mypy` are not installed in the active environment, so type-check
verification used Python bytecode compilation plus the focused test slice.
