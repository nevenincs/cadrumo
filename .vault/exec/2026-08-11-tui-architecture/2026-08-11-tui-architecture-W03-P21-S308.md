---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:e1be89ea9f2c2a84dde2d5eb5a91c0b738f6e5a0441501d1fc90fa373b1dfd53'
step_id: 'S308'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give modelo 347 clave C a real source: an amount collected on behalf of a third party -- professional fees or intellectual, industrial and authorship rights collected by an entity for its members, associates or colegiados, which RD 1065/2007 art. 32.c names explicitly and which carries its own 300,51 euro threshold rather than the general one -- is declarable under its own clave, but no transaction-level fact distinguishes a collection made for a third-party beneficiary from an ordinary sale; add that classification, settle whether the declared counterparty is the beneficiary whose fees were collected rather than the invoiced payer, and prove the lower threshold applies to it alone

## Scope

- `the invoice and profile domain facts each clave requires`
- `the modelo 347 clave classifier`
- `the contraparte row bindings in both revisions`
- `and grounded per-clave classification tests`

## Changes

- `M` `src/cadrumo/domain/invoices/_models.py` -- new `Invoice.collected_on_behalf_of_tax_id` and `collected_on_behalf_of_name` fields (RD 1065/2007 art. 34.g): when set, this invoice is a clave-C collection and the declared M347 counterparty is the beneficiary, not the invoice's own counterparty
- `M` `src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py` -- both new fields added to the strict roundtrip fixture and its assertions
- `M` `src/cadrumo/application/invoices/_source_resolver.py` -- `_m347_operation_clave` now classifies clave C first (requires BOTH `invoice.collected_on_behalf_of_tax_id` set AND the filer's `THIRD_PARTY_FEE_COLLECTOR` role, neither alone sufficient); `_m347_invoice_observation` now takes `context`, calls `_m347_filer_declaration_roles(context.bucket_id)` (S313's loader, its first real consumer), and substitutes `party_tax_id`/`party_legal_name` with the beneficiary identity when the clave is C
- `M` `src/cadrumo/application/invoices/tests/test_source_resolver.py` -- updated the two F/G discrimination tests to pass `context=` (now required); new `test_m347_clave_c_declares_the_beneficiary_not_the_payer_through_the_real_resolver` (a real seeded profile with the role, an invoice with the beneficiary fact, asserting clave C and beneficiary identity, alongside an ordinary invoice from the SAME filer staying clave B) and `test_m347_clave_c_requires_the_filer_role_a_beneficiary_fact_alone_is_not_enough` (the beneficiary fact alone, with no profile role, does not become clave C)
- `M` `src/cadrumo/domain/calculations/registry/_m347_threshold.py` -- refactored to one shared `_declarable_party_ids(totals, *, floor)` comparison; added `m347_clave_c_declarable_party_ids` (300,51 EUR floor) alongside the existing `m347_declarable_party_ids` (3.005,06 EUR floor), both now delegating to the same comparison
- `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py` -- new `_m347_row_family_threshold_filter`, replacing `_build_contraparte_clave_rows`'s S319 single-floor filter: splits observations by clave C vs. everything else, judges each against its OWN floor per party/beneficiary, and filters observation-by-observation (never a flat party-id membership test) so a party clearing only the lower clave-C floor does not silently let their below-general-floor ordinary rows through too
- `M` `src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py` -- new `test_clave_c_uses_its_own_lower_floor_alongside_the_general_one` (parametrized across both revisions): a below-clave-C-floor beneficiary produces no row, an above-floor one does, and the below-floor beneficiary's UNRELATED clave-B operation (above the clave-C floor, below the general one) also produces no row, proving the two floors do not leak into each other
- `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; bundled_authority()"` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests -q -m unit -k "347 or invoice or binding_selector or counterpart or clave or contraparte or m349 or legal_grounding or source_kind or taxonomy" src/cadrumo/application/invoices/tests/test_source_resolver.py src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py src/cadrumo/domain/deadlines/tests/test_taxpayer_model.py` -> `pass` (316 passed)

## Notes

Claves D and E remain unbuildable within this Step -- tracked separately as
`W03.P21.S309` -- and still return `None` from `_m347_operation_clave`,
exactly as before. This Step's own beneficiary-identity fact
(`collected_on_behalf_of_tax_id`/`_name`) and threshold split
(`_m347_row_family_threshold_filter`) are specific to clave C and are not
reused by D/E, whose facts (the filer's own entity type, and a subvención
transaction-level fact for E) are unrelated.

## Provenance

Most of this Step's code (Invoice model, source resolver, threshold
module, invoice_bindings.py, roundtrip and source-resolver tests) landed
captured inside a peer commit, `566c7527c0 fix(invoices): tighten the M347
threshold and source resolver bindings`, committed between this Step's
edits and this Step's own commit attempt. Only the export-parity test file
landed in this Step's own commit, `87d4e40124`. Content confirmed correct
and complete at HEAD by test run, not by diffing local edit history.
