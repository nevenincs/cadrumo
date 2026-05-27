---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
step_id: 'S03'
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

# `secure-object-backlog-drain` `P02.S03`

Repaired the invoice secure-storage roundtrip tests with explicit
repository injection.

- Modified: `src/aeat/domain/invoices/test_secure_storage_roundtrip.py`
- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain-r3/2026-05-22-secure-object-backlog-drain-r3-P02-S03.md`

## Description

Removed pytest monkeypatch database routing from the invoice
anti-tautology proof and replaced default invoice repository construction
with `InvoiceCatalogueRepository(objects=...)`. Both invoice tests now
build real SQLite engines from `Settings(aeat_database_url=...)`, create
`SecureObjectRepository(engine=...)`, and inject that repository into the
real production repository. The tampered identity proof still mutates the
persisted secure-object payload before load.

## Tests

`uv run ruff check
src/aeat/domain/invoices/test_secure_storage_roundtrip.py` passed. A
targeted search found no `monkeypatch`, `MonkeyPatch`,
`AEAT_DATABASE_URL`, `os.environ`, default `SecureObjectRepository()`,
default `InvoiceCatalogueRepository()`, or stale `noqa` in the repaired
file.
