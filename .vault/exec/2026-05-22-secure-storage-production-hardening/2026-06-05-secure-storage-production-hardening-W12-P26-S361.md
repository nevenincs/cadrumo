---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S361'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S361 - Close AFR-259 for renta substrate

Scope: close `AFR-259` for `src/aeat/domain/renta/_substrate.py` with scanner signal
`remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Audited `_substrate.py` for remote-provider, secure-storage, active-profile,
  settings, environment, filesystem, and runtime repository behavior.
- Confirmed the module defines closed `StrEnum` catalogues for Renta substrate axes:
  `RentaIncomeType` and `EstimacionDirectaModalidad`.
- Confirmed it does not call remote providers, mirror remote data, instantiate
  repositories, resolve active profiles, read settings, access environment variables,
  or perform filesystem IO.
- Preserved the scanner signal in the register history and closed it explicitly as a
  remote-provider false positive rather than deleting the row from scope.
- Closed `W12.P26.S361` through `vaultspec-core vault plan step check` and updated
  the `AFR-259` register status to `closed`.

## Outcome

`AFR-259` is closed. No production code change was required because `_substrate.py` is
a pure domain enum/catalogue module and has no remote mirror or secure-storage
responsibility.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/renta/_substrate.py`

## Notes

The plan's `remote-provider` signal is retained as scanner provenance. The closeout
disposition is that the signal was a false positive for this file.
