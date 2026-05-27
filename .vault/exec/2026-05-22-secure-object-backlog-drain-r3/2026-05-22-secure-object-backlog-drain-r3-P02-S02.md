---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
step_id: 'S02'
related:
  - '[[2026-05-22-secure-object-backlog-drain-r3-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `secure-object-backlog-drain` `P02.S02`

Repaired the submission secure-storage roundtrip tests with explicit
repository injection.

- Modified: `src/aeat/domain/submission/test_secure_storage_roundtrip.py`
- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain-r3/2026-05-22-secure-object-backlog-drain-r3-P02-S02.md`

## Description

Removed pytest monkeypatch database routing from both submission
roundtrip proof tests. Each test now builds its real SQLite engine from
`Settings(aeat_database_url=...)`, constructs
`SecureObjectRepository(engine=...)`, and injects it into the real
`SubmissionRepository`. The anti-tautology proof still mutates the
persisted secure-object payload and verifies the deleted
`justificante_csv` drift surfaces on load.

## Tests

`uv run ruff check
src/aeat/domain/submission/test_secure_storage_roundtrip.py` passed. A
targeted search found no `monkeypatch`, `MonkeyPatch`,
`AEAT_DATABASE_URL`, `os.environ`, default `SecureObjectRepository()`,
or default `SubmissionRepository()` construction in the repaired file.
