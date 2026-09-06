---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:2347aa3025bb68abaa5b80a7a02f30bd63e9606e88a649c1fff7fa0584bd2f2c'
step_id: 'S23'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Publish the drive-entries module so the duplicate it caused can become an import: the canonical OWNERSHIP_KEY and OWNERSHIP_VALUE lived in a private underscore module, which a cross-package consumer may not import, so the storage adapter carried its own copies and the duplicate was the symptom of a placement problem rather than laziness; rename the module public, update every referrer atomically including the generated api stubs, and replace the copies with an import of the canonical home

## Scope

- `src/cadrumo/adapters/outbound/google/drive_entries.py`

## Changes

- `R` `src/cadrumo/adapters/outbound/google/_drive_entries.py -> src/cadrumo/adapters/outbound/google/drive_entries.py`
- `M` `src/cadrumo/adapters/outbound/google/calc_sheets_apply.py`
- `M` `src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_drive_entries.py`
- `M` `src/cadrumo/adapters/outbound/storage/_google_drive.py`
- `R` `docs/api/cadrumo.adapters.outbound.google._drive_entries.rst -> docs/api/cadrumo.adapters.outbound.google.drive_entries.rst`
- `verify:` `uv run --no-sync ruff check src/cadrumo` -> `pass`
- `verify:` `uv run --no-sync python -m dev.docs.apidocs scaffold --check` -> `pass`

## Notes

The api stub tree was regenerated through its owning generator rather than
hand-edited. That run changed 70 stubs: 51 modules had no stub at all and 19
were stale, from modules landing without regeneration, so the drift gate was
standing red before this Step and is now conformant. Only two of the 70 belong
to this rename.

`test_storage_validation_carrier_totality_and_canonical_construction` fails
both with and without this change, on
`storage.factory:build_google_credentials has no stable validation identity`.
Establishing that took three attempts: the test timed out past 500s twice under
machine contention, and a run that completed in 8.6s against the baseline
looked like evidence the change had introduced a hang. Timing the import both
ways (2.66s with the change, 3.55s without) showed it had not.
