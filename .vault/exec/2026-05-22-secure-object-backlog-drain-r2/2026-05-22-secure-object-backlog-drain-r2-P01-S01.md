---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
step_id: 'S01'
related:
  - '[[2026-05-22-secure-object-backlog-drain-r2-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
