---
tags:
  - '#exec'
  - '#core-authority'
step_id: S76
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W08.P22.S76 - canonical sha256_file in core/hashing

## Outcome

Created `src/aeat/core/hashing.py` as the single authoritative SHA-256 file-hash
implementation for the AEAT codebase. Provides `sha256_file(path: Path) -> str`
reading in 64 KiB chunks for large-file safety.

Updated `application/filing/_export.py` line 36 to import `sha256_file` from
`...core.hashing` instead of `...adapters.inbound.pdf._utils`. This removes the
`application→adapters` edge (RELOC-019, Rule 2).

The `core/hashing.py` module also pre-lands the canonical location for
`application/ledger/_actions.py` (S77) which previously imported from the same
adapter path.

## Commit

`b41fb90a8` — refactor(filing): W08.P22.S76 - canonical sha256_file in core/hashing

## Files touched

- `src/aeat/core/hashing.py` — new canonical module
- `src/aeat/application/filing/_export.py` — sha256_file import updated

## Verification

Filing and export tests import cleanly. The `sha256_file` function is a pure
utility with no adapter dependencies.
