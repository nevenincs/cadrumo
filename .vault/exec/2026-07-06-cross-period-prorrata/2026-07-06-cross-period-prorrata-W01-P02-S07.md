---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:be5e195855ed004d3c7887bfd3442003f25cb619151bc989f7b9c2d46255cc88'
step_id: 'S07'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add the application service facade to declare, list, and get the per-ejercicio register entry, exposed only through the package top-level __all__

## Scope

- `src/aeat/application/prorrata_register/__init__.py`

## Description

- Add the `ProrrataRegisterService` application facade in `src/aeat/application/prorrata_register/__init__.py` (thin orchestration over `ProrrataRegisterRepository`) exposing `declare`, `list_all`, and `get`, all through the package top-level `__all__`.
- Pin the new production `application -> adapters` edge in the layered-architecture ledger (`.importlinter`), mirroring the `bienes_inversion` facade entry.

## Outcome

The facade composes over the encrypted repository without re-implementing any write path; `get` reads one entry by `(ejercicio, sector)` key. All five import contracts KEPT, including the layered-architecture ledger.

## Notes

The layered-architecture contract fails a new production `application -> adapters` edge loudly by design; the ledger entry `aeat.application.prorrata_register -> aeat.adapters.**` was added in alphabetical position, exactly as `aeat.application.bienes_inversion` is pinned.
