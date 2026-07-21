---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S430'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Extract one M303 settlement-period predicate and ordering authority for prorrata and bienes-de-inversion flows, preserving the legal 4T-or-0A settlement rule

## Scope

- `src/aeat/domain/iva/ src/aeat/application/calculations/ src/aeat/application/modelo/ src/aeat/application/prorrata_register/ src/aeat/**/tests/`

## Description

- Ground the legal settlement rule with `vaultspec-rag`, then read the prorrata and capital-goods calculation paths, calculate advisories, filing persistence, prorrata-register seed, and focused real-behavior tests.
- Add the IVA-domain `m303_annual_settlement_period_order()` authority, its predicate/token projections, and its production selection key: `4T` then `0A`, with later capture time breaking same-form ties. Midyear and monthly forms are not annual prorrata or capital-goods settlements.
- Route prior-definitiva carry selection, M390 capital-goods percentage lookup, prorrata and bienes calculate advisories, filed M303 register writeback, and prior-observation register seeding through the one authority.
- Preserve M390’s real stamped-M303 `4T` fallback while allowing a legal later annual settlement observation when a future registry revision supports it.
- Add a typed IVA-domain order contract for prospective `4T`/`0A` policy and a real encrypted ingress regression that verifies the current registry/repository refuses unsupported M303 `0A` before any observation is stored. Exercise all three midyear periods through real encrypted M303 filing writeback, retaining existing real advisory, seed, resolver, and M390 paths.

## Outcome

The LIVA annual-settlement rule now has one IVA-domain owner rather than six local `4T`/`0A` checks. It remains intentionally narrower than generic last-filing-period logic: monthly `12` can be a last filing for other purposes but is not a prorrata or bienes-de-inversión settlement. The domain policy prospectively orders legal settlement forms as `4T` then `0A`; the actual bundled M303 registry lifecycle currently supports only `4T`, and the encrypted repository rejects unsupported `0A` ingress before a row can be stored. Modelo 390 therefore continues to consume the real stamped-`4T` current-year percentage. No fake, mock, stub, patch, or monkeypatch was used.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/iva/_m303_settlement.py src/aeat/domain/iva/__init__.py src/aeat/application/calculations/_prorrata_regularizacion.py src/aeat/application/calculations/_bienes_inversion_regularizacion.py src/aeat/application/modelo/_prorrata_regularizacion_advisory.py src/aeat/application/modelo/_bienes_inversion_advisory.py src/aeat/application/modelo/_revision_persistence.py src/aeat/application/prorrata_register/_seed.py src/aeat/domain/iva/tests/test_m303_settlement.py src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/modelo/tests/test_prorrata_settlement_writeback.py src/aeat/application/modelo/tests/test_prorrata_regularizacion_advisory.py`
- `uv run --no-sync pytest src/aeat/domain/iva/tests/test_m303_settlement.py src/aeat/application/calculations/tests/test_observations_repository_roundtrip.py src/aeat/application/calculations/tests/test_prorrata_regularizacion.py src/aeat/application/calculations/tests/test_bienes_inversion_regularizacion.py src/aeat/application/modelo/tests/test_prorrata_regularizacion_advisory.py src/aeat/application/modelo/tests/test_bienes_inversion_advisory.py src/aeat/application/modelo/tests/test_prorrata_settlement_writeback.py src/aeat/application/prorrata_register/tests/test_seed.py src/aeat/application/calculations/tests/test_prorrata_regularizacion_source_resolver.py src/aeat/application/calculations/tests/test_prorrata_regularizacion_oracle.py src/aeat/application/modelo/tests/test_bienes_inversion_regularizacion_source_mesh_enrollment.py src/aeat/application/modelo/tests/test_prorrata_regularizacion_source_mesh_enrollment.py -q` — 71 passed.

## Notes

Independent review found and the follow-up corrected an ascending-selection defect: where both legal settlement candidates are valid, the production key selects the later legal form and then the latest capture. The typed contract proves this prospective policy without inventing a filing; a separate real encrypted ingress regression proves the present M303 `0A` registry gap fails closed and leaves no persisted row. The real stamped `4T` fallback remains authoritative until a registry-backed M303 `0A` lifecycle exists. The plan checkbox is intentionally unchanged pending coordinated reconciliation.
