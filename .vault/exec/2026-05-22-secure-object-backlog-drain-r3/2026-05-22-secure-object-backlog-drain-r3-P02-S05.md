---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
step_id: 'S05'
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

# `secure-object-backlog-drain` `P02.S05`

Repaired the modelos work-unit secure-storage roundtrip tests with
explicit repository injection.

- Modified: `src/aeat/domain/modelos/test_secure_storage_roundtrip.py`
- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain-r3/2026-05-22-secure-object-backlog-drain-r3-P02-S05.md`

## Description

Removed pytest monkeypatch database routing from the lifecycle-drift
proof and replaced default work-unit repository construction with
`WorkUnitCatalogueRepository(objects=...)`. Both tests now inject a real
`SecureObjectRepository(engine=...)` built from
`Settings(aeat_database_url=...)`. The lifecycle anti-tautology proof
still mutates persisted secure-object payload state before load.

## Tests

`uv run ruff check
src/aeat/domain/modelos/test_secure_storage_roundtrip.py` passed. A
targeted search found no `monkeypatch`, `MonkeyPatch`,
`AEAT_DATABASE_URL`, `os.environ`, default `SecureObjectRepository()`,
default `WorkUnitCatalogueRepository()`, or stale `noqa` in the repaired
file.
