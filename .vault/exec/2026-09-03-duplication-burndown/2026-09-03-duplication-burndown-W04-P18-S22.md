---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:78367b883dc945a7bc21068997805fb7581daa9a6c632657eac8a582b1f60fad'
step_id: 'S22'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Remove constant-level duplication the clone detector structurally cannot see: 34 public module-level constants carry a private same-stem copy elsewhere and 21 are literal-identical, each far below the jscpd clone threshold so the scanner reports its adjudicated floor while they stand; replace the five whose canonical home is safely importable with imports of that home, and record why the rest are not simple imports

## Scope

- `src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`

## Changes

- `M` `src/cadrumo/application/live/notification_documents.py`
- `M` `src/cadrumo/adapters/inbound/notificacion/_sancion.py`
- `M` `src/cadrumo/domain/iva/sepa_marca.py`
- `M` `src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/adapters/outbound/google -n 0` -> `fail` (4 pre-existing, identical with and without the change)

## Notes

Two duplicates were deliberately left. `domain/iva/invoice_classification`
already imports `domain.invoices`, so importing `SPAIN_COUNTRY_CODE` the other
way would close a package-level cycle. And the Google `OWNERSHIP_KEY` /
`OWNERSHIP_VALUE` copy in `adapters/outbound/storage/_google_drive.py` cannot
import its canonical home, because that home is the private module
`adapters/outbound/google/_drive_entries.py` and a cross-package import from a
private underscore module is forbidden outright. The copy exists BECAUSE the
canonical home is private; resolving it means giving those constants a public
home, which is a placement decision rather than a cleanup.

Six pre-existing failures were confirmed by copy-aside A/B, identical with and
without these edits: four in `adapters/outbound/google`
(`test_auth_preconditions`, three in `test_calc_sheets_typed_outcomes`) and two
in `application/live` (`test_censal_acquisition`, `test_iva_wallet_capture_backend`).
