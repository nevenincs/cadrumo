---
tags:
  - '#exec'
  - '#core-authority'
step_id: S75
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W08.P22.S75 - remove adapter import from _runtime_repository

## Outcome

Removed the module-scope adapter import from `application/filing/_runtime_repository.py`.

Before:
- `from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket` at module scope
- `from ...adapters.persistence.storage.sql import SecureObjectRepository` at module scope (used in type annotation)

After:
- `SecureObjectRepository` moved behind `TYPE_CHECKING` guard (annotation-only, ADR Exception C)
- `secure_object_repository_for_bucket` call deferred into the function body with `# noqa: PLC0415`

This eliminates the module-scope `application→adapters` edge (RELOC-015, Rule 2).

## Commit

`4f821dcf0` — refactor(filing): W08.P22.S75 - remove adapter import from _runtime_repository

## Files touched

- `src/aeat/application/filing/_runtime_repository.py` — adapter imports removed

## Verification

No tests directly cover `_runtime_repository.py`; the module imports cleanly and
the deferred import pattern matches the established `_get_session_store()` precedent.
