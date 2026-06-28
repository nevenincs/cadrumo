---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S10'
related:
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]'
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-adr]]'
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-research]]'
---



# `cli-workflow-redesign` `P02.S07-S10`

Completed the Modelo 145 communication vocabulary phase.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`

## Description

The existing registry vocabulary could not represent Modelo 145 cleanly because
casillas forced a `filing` application link and no communication surface
existed. Added narrow `communication` and `payer_delivery` application-link
surfaces, allowed casillas to be backed by filing or communication semantics,
and added validator rules that reject communication entries combined with
filing, deadline, live, portal, or filing schedule surfaces.

This preserves filing-grade behavior for existing modelos while creating a
non-filing registry path for Modelo 145.

## Tests

Passed:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_modelo_145_source_catalogue.py`
- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_registry_schema.py`
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_registry_schema.py`
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_registry_schema.py`
