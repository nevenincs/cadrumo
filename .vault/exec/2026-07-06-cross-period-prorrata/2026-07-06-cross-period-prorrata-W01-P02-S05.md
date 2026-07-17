---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# declare the PROFILE_PRORRATA_REGISTER FINANCIAL bucket-local secure-object namespace singleton and export it from the storage facade, mirroring PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE

## Scope

- `src/aeat/adapters/persistence/storage/_namespace_registry.py`

## Description

- Declare the `PROFILE_PRORRATA_REGISTER_NAMESPACE` FINANCIAL bucket-local secure-object singleton in `src/aeat/adapters/persistence/storage/_namespace_registry.py`, mirroring `PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE` (namespace `aeat.persistence.profile.prorrata_register`, singleton `default` key, structured-custody).
- Enroll it in the `STORAGE_NAMESPACE_REGISTRY` namespaces tuple and the module `__all__`.
- Re-export it from the storage facade `src/aeat/adapters/persistence/storage/__init__.py` (import plus `__all__`).

## Outcome

The namespace is registered and discoverable; the storage namespace-registry conformance suite recognises it (31 passed). FINANCIAL sensitivity keeps the taxpayer's per-ejercicio percentages encrypted at rest, never plaintext.

## Notes

None.
