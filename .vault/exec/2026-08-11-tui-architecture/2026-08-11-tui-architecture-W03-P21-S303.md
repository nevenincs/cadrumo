---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:9e47b9d23baa5c8598aa419bc62a4a510cbe26c6982b38f5d08ca5abd5ae2539'
step_id: 'S303'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give modelo 347 claves F and G a real source: an invoice issued or received by a travel agency acting as intermediary in another's name and account, for the mediated services RD 1619/2012's fourth additional provision enumerates, is declarable under its own clave with the direction already available from the invoice kind, but no fact records that an invoice was issued under that regime; add the closed operation-type classification on the invoice mirroring the intracommunity mechanism the M349 side already uses, ground each clave against the provision's own service enumeration, and prove an agency-mediated invoice declares under F or G by direction while an ordinary invoice of the same amount does not

## Scope

- `the invoice observation's operation-type classification`
- `the modelo 347 clave classifier`
- `the contraparte row bindings in both revisions`
- `and grounded per-direction classification tests`

## Changes

- `M` `src/cadrumo/core/aggregation.py` -- new `TravelAgencyMediationType` (StrEnum: `MEDIATED_SERVICE`, `AIR_PASSENGER_TRANSPORT`), grounded on RD 1619/2012 disposición adicional cuarta's own service enumeration
- `M` `src/cadrumo/core/__init__.py` -- lazy-export wiring for the new type
- `M` `src/cadrumo/domain/invoices/_models.py` -- new `Invoice.travel_agency_mediation: TravelAgencyMediationType | None` field
- `M` `src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py` -- new field added to the strict roundtrip fixture and its assertion (populate-every-defaultable-field discipline)
- `M` `src/cadrumo/application/invoices/_source_resolver.py` -- new `_m347_operation_clave(invoice, source_kind=...)` classifier: checks the mediation fact first (F for any ISSUED mediated invoice, G for RECEIVED air-passenger-transport only), falls through to the existing `m347_operation_clave(source_kind)` for A/B. Wired into `_m347_invoice_observation`, which previously built every `InvoiceObservation` with `operation_clave` hardcoded to `None`
- `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py` -- `m347_operation_clave`'s docstring corrected: it no longer claims to be the sole classifier for F/G (dropped a vault-stem reference in the same edit)
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/{2011-2024,2025-y-siguientes}/bindings/0002-contraparte-clave.toml` -- comment corrections: dropped vault-stem references, corrected the "only A and B classifiable" claim now that F/G are too
- `M` `src/cadrumo/application/invoices/tests/test_source_resolver.py` -- new `test_m347_clave_f_declares_a_mediated_sale_ordinary_sale_of_the_same_amount_does_not` and `test_m347_clave_g_declares_only_air_transport_purchases_not_other_mediated_purchases`; corrected `test_m347_declarable_facts_are_reachable_on_the_canonical_path`'s hand-typed `operation_clave: None` expectation to `"B"`, now that the canonical path actually classifies it
- `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; bundled_authority()"` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests -q -m unit -k "347 or invoice or binding_selector or counterpart or clave or contraparte or m349 or legal_grounding or source_kind or taxonomy" src/cadrumo/application/invoices/tests/test_source_resolver.py src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py` -> `pass` (308 passed)

## Notes

Larger than the intracommunity precedent alone suggested, for a reason
outside this Step's own scope: `m347_operation_clave` had ZERO production
callers before this change. `_m347_invoice_observation` built every
`InvoiceObservation` with `operation_clave` hardcoded to `None`, so claves
A/B -- believed wired since S294 -- were never actually classified on the
real resolver path; only tests that hand-constructed `InvoiceObservation`
ever exercised them. Corrected a comment I wrote in S294 that had
overclaimed this ("only A and B are currently classified from source_kind
alone by m347_operation_clave") without verifying the call site called it.
Fixing S303's scope (F/G) required wiring the ONE call site that determines
`operation_clave` for every invoice-sourced clave, so A/B became genuinely
live for the first time in the same change, not a separate one.

Claves C, D and E remain unbuildable within this Step -- tracked separately
as `W03.P21.S308` (C) and `W03.P21.S309` (D+E) -- and still return `None`
from both `m347_operation_clave` and `_m347_operation_clave`, exactly as
before.
