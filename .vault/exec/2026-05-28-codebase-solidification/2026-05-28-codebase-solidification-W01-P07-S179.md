---
step_id: S179
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P07.S179 — CSV encoding fallback chain constant

## Outcome

Introduced `CSV_ENCODING_FALLBACK_CHAIN: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp1252", "iso-8859-1")`
at module level in `src/aeat/core/external_constants.py` (appended before `load_external_constants`).

Migrated the inline tuple at `src/aeat/adapters/inbound/financial/providers/_csv.py:303`
from `(preferred, "utf-8-sig", "utf-8", "cp1252", "iso-8859-1")` to
`(preferred, *CSV_ENCODING_FALLBACK_CHAIN)` and added the corresponding import.

Audit finding A7.9 (CSV encoding fallback chain drift) is resolved.

## Files touched

- `src/aeat/core/external_constants.py`
- `src/aeat/adapters/inbound/financial/providers/_csv.py`

## Verification

All 11 tests in `test_csv.py` and all 32 in `test_external_constants.py` pass.
Commit: 85bf0e231. `vault plan step check` applied.
