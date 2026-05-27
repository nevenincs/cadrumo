---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
step_id: 'S01'
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

# `secure-object-backlog-drain` `P01.S01`

Inventoried the R3 secure-storage roundtrip candidates and selected the
exact repaired files.

- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain-r3/2026-05-22-secure-object-backlog-drain-r3-P01-S01.md`

## Description

Selected four remaining P02.S06 hygiene exceptions:
`src/aeat/domain/submission/test_secure_storage_roundtrip.py`,
`src/aeat/domain/invoices/test_secure_storage_roundtrip.py`,
`src/aeat/domain/justificante/test_secure_storage_roundtrip.py`, and
`src/aeat/domain/modelos/test_secure_storage_roundtrip.py`. Each file
uses a real `EphemeralMasterKeyProvider` and SQLite secure-object
storage. The repair scope is routing-only: inject
`SecureObjectRepository(engine=...)` into the real repository under test
and remove any pytest monkeypatch or raw database environment routing.

## Tests

Ran `uv run vaultspec-core vault plan check` and `status` for the R3
plan. Confirmed all four selected files remain in the explicit pending
hygiene classification map before repair.
