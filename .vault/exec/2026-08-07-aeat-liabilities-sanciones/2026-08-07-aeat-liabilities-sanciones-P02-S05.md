---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:2fc8c729d2297767b66863bbf7aee046d484caa980108c73c9e0253638060d5e'
step_id: 'S05'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Add DeudasCapture, PersistedDeudasSnapshot, deudas_snapshot_object_key and _derive_snapshot_id mirroring the ExpedientesCapture/PersistedExpedientesSnapshot pattern exactly

## Scope

- `src/cadrumo/application/live/_deudas.py`

## Description

Added `DeudasCapture`, `PersistedDeudasSnapshot`, `deudas_snapshot_object_key`
and the content-addressed `_derive_snapshot_id`, mirroring the
`ExpedientesCapture` / `PersistedExpedientesSnapshot` pattern.

## Outcome

Modified files:

- `src/cadrumo/application/live/_deudas.py` (new)
- `src/cadrumo/application/live/__init__.py` (`TYPE_CHECKING` block, lazy
  `__getattr__` branch, `__all__`)
- `src/cadrumo/core/errors/registry/_domain_part1.py` (error-code entry for
  `DeudasSnapshotNotFoundError`)
- `docs/api/cadrumo.application.live._deudas.rst` and the live stub index

`DeudasCapture` carries `mode='read'` as the structural assertion that a
capture cannot drive an AEAT-side mutation, which is load-bearing here because
the payment controls sit beside the listing the capture comes from. The id is
derived from the canonical capture JSON, so an identical re-read dedupes.

Symbols resolve through the package's existing lazy `__getattr__`, matching how
the expedientes, notifications and verify services are already exposed, so the
module-load-time profile is unchanged.

## Verification

Covered by `test_deudas_service.py` (see `S07`). Commit `685abbf6b4`,
`202 0 src/cadrumo/application/live/_deudas.py`,
`34 0 src/cadrumo/application/live/__init__.py`,
`11 0 src/cadrumo/core/errors/registry/_domain_part1.py`.

## Notes

A new `CadrumoError` subclass is refused at class-creation time unless it has an
error-code registry entry, so `DeudasSnapshotNotFoundError` required one in the
same change. That entry declares
`message_key="errors.refused.refused_live_deudas_snapshot_not_found"`, which is
one of the five unenrolled locale keys recorded in `S07`'s notes.
