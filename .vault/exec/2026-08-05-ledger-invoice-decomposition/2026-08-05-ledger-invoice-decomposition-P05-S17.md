---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:890518d852fcc57b39f480899694caf526b52bd3e487b9d7abfc43a426706514'
step_id: 'S17'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Add strict roundtrip coverage for every new persisted field, with an anti-tautology proof that a deleted field is refused on load

## Scope

- `src/cadrumo/application/calculations/tests`

## Description

- Inventory every field the campaign added, by diffing each landing against the campaign's first commit and reading the models rather than trusting the step titles.
- Record that none of them is persisted, and that the invoice retencion fields predate the campaign with non-default roundtrip coverage already in place.
- Add `src/cadrumo/application/aggregation/tests/test_invoice_retencion_store_roundtrip.py` for the new KIND of row the invoice routing made writable in the per-perceptor store.
- Assert strict equality across that encrypted boundary rather than a field spot check, with the observation's one defaultable field populated non-default.
- Add an on-disk drop proof for the store, carrying a positive control, because the existing anti-tautology gate there validates the payload model against a partial dict and never persists mutated bytes.
- Prove separately that dropping the defaultable field loads but reloads UNEQUAL, which is why the roundtrip asserts equality rather than presence.
- Add `src/cadrumo/domain/invoices/tests/test_retencion_persistence_invariant.py` pinning both halves of the retencion consistency contract after persistence.
- Probe every refusal to confirm it names the invariant under test rather than an unrelated validator.

## Outcome

Landed as commit `a35f49fd65` (2 files, +407, 0 deletions).

Raw counts, serial runs (`-n 0`): the two new modules 6 passed, 0 failed, 0 skipped; together with the three neighbouring persistence suites they exercise, 42 passed, 0 failed, 0 skipped. `domain/invoices/tests` 126 passed, 0 failed, 0 skipped. `application/aggregation/tests` 610 passed, 0 failed, 0 skipped, 7 deselected by the unit lane's marker expression.

The inventory is the substantive part of the step and its answer is that the campaign introduced no new persisted field. The income grounding marker and the withholding derivation sit on an aggregation observation whose only consumers are the pipeline that builds it and the registry resolver that folds it, with no repository anywhere; the Axis-A component table is declared module data; the invoice decomposition is a derived projection with no production consumer outside its own package; the received-invoice routing writes the pre-existing observation shape and added no field to it; and the invoice retencion fields predate the campaign, already populated at non-default values by the existing catalogue roundtrip. Manufacturing coverage for a field that does not cross a boundary would have produced a green gate protecting nothing.

What the campaign did open is two gaps on shapes that already existed, and both are closed here. Routing made a row writable whose source kind is an invoice rather than a ledger transaction, a combination no roundtrip had carried across the boundary. The retencion consistency contract became an invariant that had never been tested after persistence, which matters because an invoice reaches the routing step after a save and a load, not straight from construction.

## Notes

The step's declared scope named `src/cadrumo/application/calculations/tests`. The campaign touched nothing in that package, so the two modules were placed at the packages that own the boundaries they exercise, per the narrowest-owning-package convention. Recording the deviation rather than following the directory hint into a package with no stake in the behaviour.

The invoice invariant gap is not cosmetic, and the concrete failure is worth stating. Were a stored invoice able to load carrying a retencion rate with no amount, the routing step would read the absent amount as "this invoice declares no retencion" and exclude the liability. A real withholding would drop out of Modelo 111, arriving through a record shape the validator asserts cannot exist. The refusal probe confirms the load is refused by exactly that invariant.

### Refusal probes

Each mutation was persisted through the production encryption path and re-read through the production read path, and the resulting error inspected rather than assumed:

- Invoice with `retention_amount` deleted beside a surviving rate: refused, naming the rate-requires-amount invariant.
- Invoice with `retention_amount` raised one cent above the base: refused, naming the base-imponible bound.
- Retencion observation with `retencion_amount` deleted: refused as a missing required field on the observation inside the envelope payload.
- Retencion observation with the defaultable `perceptor_name` deleted: loads, and reloads unequal. This is the case a field-by-field spot check would miss entirely, and it is why the roundtrip compares whole records.
- Unmutated control for each: loads back equal, so no refusal above can be attributed to the mutation procedure itself.
