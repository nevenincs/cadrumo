---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
modified: '2026-07-17'
body_hash: 'sha256:9ec9a336266293bc49934c2bec9a4ce7e63b3605e2ead62b8a074db11188da59'
step_id: 'S01'
related:
  - '[[2026-05-22-secure-object-backlog-drain-r2-plan]]'
---

# `secure-object-backlog-drain` `P01.S01`

Inventoried the R2 secure-SQL hygiene candidates and selected the exact
repaired files.

- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain-r2/2026-05-22-secure-object-backlog-drain-r2-P01-S01.md`

## Description

The R2 slice targets `src/aeat/domain/submission/test_repository.py` and
`src/aeat/domain/invoices/test_repository.py`. Both files still use an
autouse `pytest.MonkeyPatch` fixture to set `AEAT_DATABASE_URL`; both
also instantiate default secure-object backed repositories in tests.
The repair pattern is explicit secure-object repository injection backed
by `create_engine_from_settings(Settings(aeat_database_url=...))`.

## Tests

Ran `uv run vaultspec-core vault plan check` and `status` for the R2
plan. Ran a targeted search over the selected files and hygiene guard to
confirm the monkeypatch and default-constructor repair scope.
