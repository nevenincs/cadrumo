---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:cb2017f1731d950308c8dd5c5bc6aca6fb5ee03294f2d673fdf83018eb18aa5d'
step_id: 'S89'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Fix the violations the unblinded gates exposed: a CLI payload re-implementing ISO date parsing, two stale persisted-version exemptions, and one over-granted bool exemption

## Scope

- `src/cadrumo/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `M` `src/cadrumo/tests/test_parsing_enrollment_inventory.py`
- `M` `src/cadrumo/core/tests/test_persisted_version_single_declaration.py`
- `verify:` `pytest src/cadrumo/tests/test_parsing_enrollment_inventory.py src/cadrumo/core/parsing -n 0 -m ""` -> `pass`

## Notes

One exposed violation is deferred: the bare `date.fromisoformat` in
`application/modelo/_edit_services.py` is fixed in the working tree but that
file already imports from modelos modules the commit does not carry, so it
rides with the modelos commit.
