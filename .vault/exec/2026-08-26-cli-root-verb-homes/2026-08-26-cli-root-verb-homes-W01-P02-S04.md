---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:073471abb03e6c6c5a59cc22ac08d5a16bba3ffed05b59002ddee190780ad45b'
step_id: 'S04'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Declare remote-handle locus on folder, reference and spreadsheet-id parameters

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_app_ledger_management_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_google_command_specs.py`
- `verify:` `COMMAND_GRAPH rebuild + ruff check` -> `pass`

## Notes

Four `reference` parameters are deliberately left at `TransportLocus.NONE`:
`app ledger evidence review show` and the three `app ledger prorrata` leaves. They
carry IVA prorrata and review record references, not remote handles, so a
remote-handle declaration there would be false.
