---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:931b9cbd00d3529a74e13a7842f68e9dde9975295047e18ea5ed0dda4f987613'
step_id: 'S18'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Carry both limits LIRPF art. 30.2.5.a states for the seguro de enfermedad by widening the statutory-cap variant to an annual per-person amount alongside its daily one, declaring the 500 and 1.500 limbs in the corpus, and summing each limb over its own population, with an uncounted caller falling back to the ordinary limb so widening the rule regresses nobody

## Scope

- `src/cadrumo/domain/categories/ and src/cadrumo/domain/renta/ and src/cadrumo/_data/registry/aeat/categories/profiles.toml`

## Changes

- `M` `src/cadrumo/domain/categories/_proportionality.py`
- `M` `src/cadrumo/domain/categories/_registry.py`
- `M` `src/cadrumo/_data/registry/aeat/categories/profiles.toml`
- `M` `src/cadrumo/domain/renta/_ledger_expenses.py`
- `M` `src/cadrumo/domain/categories/tests/test_registry.py`
- `M` `src/cadrumo/domain/renta/tests/test_ledger_expenses.py`
- `A` `src/cadrumo/domain/categories/tests/test_seguro_enfermedad_discapacidad_limb.py`
- `A` `src/cadrumo/domain/renta/tests/test_seguro_cap_sums_both_limbs.py`
- `verify:` `pytest src/cadrumo/domain/categories src/cadrumo/domain/renta src/cadrumo/domain/tests` -> `pass`
- `verify:` `out-of-tree mutation of the shipped corpus, 3 proofs plus control` -> `pass`

## Notes

The variant concept was WIDENED, not duplicated. A variant already meant a cap
selected by a legally relevant condition; only its unit was daily, because dietas was
the first user. RIRPF art. 9 states daily amounts and LIRPF art. 30.2.5.a states annual
per-person ones, so the variant now carries exactly one of the two units and a rule's
variants must agree on which. The dietas shape is unchanged and a test pins that.

An annual variant set applies EVERY variant at once to its own share of the insured
persons, unlike a daily set where one condition selects one amount. That is what the
article means by 500 per person or 1.500 for each with discapacidad in the same return.

THE HALF THIS DOES NOT DELIVER, stated plainly. Production never populates the person
counts: the only construction site of RentaDeductibilityContext, in
application/aggregation/_renta_ledger.py, sets profile_year, usage_ratios,
residence_ccaa and iva_deduction_ratio and leaves statutory_cap_person_count at its
default of 1. So the shipped behaviour today is a flat 500 for the contribuyente, and
it remains so after this step. What changed is that the lawful answer is now
expressible and computed correctly when the counts are supplied; wiring the family
profile through to that context is separate work and is recorded as such in the
feature audit rather than counted as done here.

Three existing tests asserted the retired flat shape and were updated to the two-limb
contract rather than deleted: the registry semantics test, the ledger cap test, and
the regulatory-cap-binds gate, which reds if a cap stops binding. That gate is why the
uncounted fallback exists at all -- returning None there would have made the seguro cap
bind nothing.
