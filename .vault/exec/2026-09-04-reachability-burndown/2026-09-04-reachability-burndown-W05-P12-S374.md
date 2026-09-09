---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:efa0184d1540f0b910f00476862697558c38abe69a1faf2ca2c8dcd6bf790517'
step_id: 'S374'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unconsumed AttachmentCatalogue aggregate and its catalogue-only coercion and collection vocabulary.

## Scope

- `attachment domain models`
- `attachment store and service tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/domain/attachments/models.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/attachments/models.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/domain/attachments/tests -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
