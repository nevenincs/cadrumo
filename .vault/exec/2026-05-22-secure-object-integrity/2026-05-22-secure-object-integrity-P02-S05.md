---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S05'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---




# `secure-object-integrity` `P02.S05`

Added a static hygiene guard for ephemeral master keys and default secure-object repositories.

- Created: `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`

## Description

Added a source-hygiene test that parses test modules under `src/aeat` and detects files that combine actual `EphemeralMasterKeyProvider` constructor calls with default SQL-backed secure-object repository use. The guard covers direct `SecureObjectRepository()` and known indirect wrappers that default internally to the process SQL repository, including the filed-declaration observation store aliases. Such files must declare an autouse temp SQLite `AEAT_DATABASE_URL` fixture with engine disposal, use explicit repository injection, or remain in the P02.S06 pending backlog.

The guard is intentionally static and non-mutating. It does not write encrypted rows, change process environment, or introduce fakes, stubs, mocks, skips, xfails, or monkeypatch-based shortcuts. Review remediation replaced raw substring checks with AST call detection and moved the existing discovered file-level backlog into an explicit P02.S06 pending inventory so new unclassified files fail immediately.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`
- `uv run pytest src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`

The focused guard run passed 1 test and reported no new unclassified violations beyond the explicit P02.S06 pending inventory.
