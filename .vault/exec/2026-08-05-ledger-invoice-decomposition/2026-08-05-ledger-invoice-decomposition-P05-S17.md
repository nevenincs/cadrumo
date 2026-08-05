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

Each mutation is persisted through the production encryption path and re-read through the production read path, and the resulting error is inspected rather than assumed:

- Invoice with `retention_amount` deleted beside a surviving rate: refused, naming the rate-requires-amount invariant.
- Invoice with `retention_amount` raised one cent above the base: refused, naming the base-imponible bound.
- Retencion observation with `retencion_amount` deleted: refused as a missing required field on the observation inside the envelope payload.
- Retencion observation with the defaultable `perceptor_name` deleted: loads, and reloads unequal. This is the case a field-by-field spot check would miss entirely, and it is why the roundtrip compares whole records.
- Unmutated control for each: loads back equal, so no refusal above can be attributed to the mutation procedure itself.

### Revision after code review

Two blocking items came back, both confined to the invoice invariant module, and both are now fixed on disk.

The first is the more serious and the claim above is what it landed on. As originally committed, the probes lived only in the throwaway scratch script that produced this list; the committed tests asserted merely that SOME `ValidationError` fired. That gap is real rather than pedantic: had the retencion consistency contract been deleted while a mutated payload tripped an unrelated invoice validator, both tests would have stayed green while the invariant they exist for was gone, and its failure mode is a genuine Modelo 111 withholding dropping out. The refusal is now captured and asserted against the field identifiers the failing invariant names, which is structure rather than prose and survives any rewording. A discrimination probe confirms it bites: mutating an unrelated field raises the invoice-identity validator, whose message satisfies neither expected name set, so the deletion scenario now reddens. The same upgrade went onto the store module's drop proof, where the pydantic `loc` and `type` answer the question structurally.

The second was a false justification rather than a behavioural defect. The module restated the invoice namespace, object key and schema version as literals under a comment claiming those names were private to their owning adapter. The premise was simply wrong: `INVOICE_CATALOGUE_NAMESPACE` is exported from the storage facade, and the sibling module landed in the same commit already imports the analogous retencion namespace from that exact facade. All four values now derive from the facade definition, including the sensitivity class, so the proofs cannot go on mutating bytes nothing reads if the namespace ever moves. Worth recording that the comment was not a harmless inaccuracy: it argued FOR the duplication, so a later reader would have taken the restatement as considered rather than as the oversight it was.

A third item came back on re-review, and it is the sharpest of the three because the first fix created it. Asserting the two field identifiers for the base-bound case does not discriminate WITHIN the contract: two clauses name both `retention_amount` and `base_total`, the bound itself and the rate-agreement check that follows it, so an inflated amount sitting beside its rate is refused by either and the assertion cannot say which answered. Deleting the bound left the test green, while the docstring claimed it pinned the answering clause. The mutation now deletes the stored rate alongside inflating the amount: the rate-agreement clause applies only when a rate is present, so the bound becomes the only clause able to refuse. Measured both ways -- with the bound made unreachable, the old mutation still satisfied the name set through the neighbouring clause, and the new mutation produces no refusal at all, so the test reddens.

The docstring was rewritten rather than merely left true. The original argued from clause ORDER, which held today and would have quietly stopped holding after any reorder; the guarantee is now inapplicability, which does not depend on sequence. That distinction is the same one the second finding turned on, arriving from the opposite direction: there a false reason defended a real defect, here a fragile reason would have defended a real guarantee. Both leave a later reader with a justification that has outlived its evidence.

Raw counts after the revision, serial (`-n 0`): the two modules 6 passed, 0 failed, 0 skipped.
