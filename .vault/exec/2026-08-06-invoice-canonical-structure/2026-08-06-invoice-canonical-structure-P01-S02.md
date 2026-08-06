---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:9284aae70bbc6de0e8cf2f9fa77387fa77d4415b51eaecd902be7a5ffb07ff94'
step_id: 'S02'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Record that canonical M349 party identity is already conserved structurally and do NOT add eu_iva_id to the canonical aggregate, because a non-ES counterparty_country forces counterparty_tax_id to be that country's published NIF-IVA through the central NIF_IVA_FORMATS authority including the GR to EL prefix mapping, so a second identity field would install a second party-identity authority on the one axis where a disagreement mis-declares an intra-community operator, then hand the slim eu_iva_id versus counterparty_nif disagreement to the fold rule in S08 as a record class rather than a missing field

## Scope

- `src/cadrumo/domain/invoices/_models.py`

## Description

- Re-measured this Step's stated premise at `HEAD` before executing it, per the plan's instruction that inherited citations are line-drifted.
- Found the premise false and did NOT add the field, recording the measurement and re-scoping the Step instead.
- Pinned the conserving mechanism as an executable refusal proof under the preceding Step rather than as prose.
- Handed the live question this Step carried to the fold-rule Step as a record class.

## Outcome

**No field was added, and adding one would have introduced a defect.** This Step was premised on the canonical aggregate lacking the slim path's EU-VAT-ID preference and country-prefix derivation. It does lack both, and needs neither.

The canonical counterparty normaliser validates a non-`ES` counterparty tax id against that country's published NIF-IVA pattern, so on a canonical record the counterparty tax id already IS the EU VAT number. The counterparty country is a required first-class field, so nothing needs deriving from a prefix, and the Greek ISO-versus-VAT split is resolved by the same central identity authority that maps the ISO code to the VAT prefix.

The slim store needs a separate identity field precisely because it couples neither axis. Adding the same field to the canonical aggregate would install a **second party-identity authority** on the record, two fields able to disagree about who was invoiced, on the one axis where a disagreement mis-declares an intra-community operator on a recapitulative return. That is the duplication class this campaign exists to remove.

Consequences for the plan, both recorded in it:

- This Step was named a hard precondition of the deletion phase and the sharpest instance of the ordering constraint. It is neither. **The deletion phase is unblocked on this axis.**
- The live question does not disappear. A slim record whose domestic NIF and EU VAT ID disagree is an unmigratable record class for the fold rule, not a missing canonical field, and the fold must state whether it refuses, quarantines or resolves it. It must not silently pick one: the two identifiers name different parties.
- A further population is now expected that a field-list inventory cannot see. The canonical model is **stricter** on this axis, so the fold will meet slim records it refuses outright, namely any record pairing a domestic-format NIF with a foreign country. This is why the capability inventory was rescoped to defaults and nullability.

## Verification

The re-scope is evidenced by the executable refusal proof landed under the preceding Step, not by this record's prose:

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_source_resolver.py -p no:randomly -q --no-header
    21 passed in 22.02s

The proof that pins this Step's conclusion is `test_canonical_invoice_refuses_the_tax_id_country_mismatch_slim_permits`, which asserts the canonical model rejects the shape the slim model accepts, matched on the refusal message so it proves the country/tax-id coupling fired rather than merely that some validator did. If that coupling were ever relaxed, the proof reddens and this Step's conclusion is retired with it.

## Notes

This Step is closed as re-scoped, not as implemented. The plan's governing rule for this phase is that a criterion found already satisfied must be recorded and re-scoped rather than silently ticked, and this is that case, with the added weight that executing the Step as written would have added a second identity authority rather than closed a gap.

The original criterion is preserved in the plan's Verification section alongside the correction, so a later reader can see what was believed, what was measured, and why the conclusion changed.
