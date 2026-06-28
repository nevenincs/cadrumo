---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S02'
related:
  - '[[2026-05-22-secure-object-backlog-drain-r2-plan]]'
---



# `secure-object-backlog-drain` `P02.S02`

Repaired the domain submission repository tests with settings-backed
secure-object repository injection.

- Modified: `src/aeat/domain/submission/test_repository.py`
- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain-r2/2026-05-22-secure-object-backlog-drain-r2-P02-S02.md`

## Description

Removed the autouse `pytest.MonkeyPatch` database fixture and replaced
default repository construction with an injected `SecureObjectRepository`
backed by `create_engine_from_settings(Settings(aeat_database_url=...))`.
The secret-store and ephemeral master-key behavior remains real; no fake
repository or mocked storage path was introduced.

## Tests

`uv run ruff check src/aeat/domain/submission/test_repository.py` passed.
A targeted search found no `monkeypatch`, `MonkeyPatch`,
`AEAT_DATABASE_URL`, `os.environ`, default `SecureObjectRepository()`,
or default `SubmissionRepository()` construction in the repaired file.
