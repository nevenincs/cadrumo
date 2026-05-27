---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
step_id: 'S04'
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

# `secure-object-backlog-drain` `P02.S04`

Repaired the justificante secure-storage roundtrip test with explicit
repository injection.

- Modified: `src/aeat/domain/justificante/test_secure_storage_roundtrip.py`
- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain-r3/2026-05-22-secure-object-backlog-drain-r3-P02-S04.md`

## Description

Replaced default `JustificanteRepository()` construction with
`JustificanteRepository(objects=...)` backed by
`SecureObjectRepository(engine=...)`. The test continues to exercise real
SQLite secure-object storage, a real ephemeral master key, and strict
field-level roundtrip witnesses.

## Tests

`uv run ruff check
src/aeat/domain/justificante/test_secure_storage_roundtrip.py` passed. A
targeted search found no `monkeypatch`, `MonkeyPatch`,
`AEAT_DATABASE_URL`, `os.environ`, default `SecureObjectRepository()`,
or default `JustificanteRepository()` construction in the repaired file.
