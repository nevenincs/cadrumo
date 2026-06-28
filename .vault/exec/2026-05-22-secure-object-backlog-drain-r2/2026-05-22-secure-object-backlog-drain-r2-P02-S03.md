---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S03'
related:
  - '[[2026-05-22-secure-object-backlog-drain-r2-plan]]'
---



# `secure-object-backlog-drain` `P02.S03`

Repaired the invoice and transaction catalogue roundtrip tests with
settings-backed secure-object repository injection.

- Modified: `src/aeat/domain/invoices/test_repository.py`
- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain-r2/2026-05-22-secure-object-backlog-drain-r2-P02-S03.md`

## Description

Removed the autouse `pytest.MonkeyPatch` database fixture. The tests now
use `create_engine_from_settings(Settings(aeat_database_url=...))` and
pass `SecureObjectRepository(engine=...)` into the real invoice and
transaction catalogue repositories. The persisted roundtrip assertions
still execute against real SQLite secure-object storage.

## Tests

`uv run ruff check src/aeat/domain/invoices/test_repository.py` passed.
A targeted search found no `monkeypatch`, `MonkeyPatch`,
`AEAT_DATABASE_URL`, `os.environ`, default `SecureObjectRepository()`,
or default invoice repository construction in the repaired file.
