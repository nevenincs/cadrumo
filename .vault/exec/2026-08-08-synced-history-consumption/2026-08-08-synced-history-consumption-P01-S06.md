---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:202eed23ea1ec37881579e3603b7256f38c056f2bcd6401f11b4fbeb834713f2'
step_id: 'S06'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---

# Probe the over-payment direction deliberately

## Scope

- `src/cadrumo/application/modelo`
- `src/cadrumo/application/calculations`

## Description

- Establish the DIRECTION of error a synced-but-unconsumed history produces, by
  asking what kind of quantity each unconsumed carry is rather than assuming.
- Enumerate every diagnostic reason in the closed taxonomy that watches the
  over-payment direction, and find where each is actually raised.
- Read what each of the two carry resolvers returns when it cannot satisfy a
  binding, rather than reading the resolver's docstring.

## Outcome

YES, a synced-but-unconsumed history over-declares, and the direction is
structural rather than incidental. Every carry the census found is a quantity
that REDUCES the taxpayer's liability: pagos fraccionados already paid, retenciones
already suffered, prior negative results and bases imponibles negativas carried
forward, IVA compensación pending from an earlier period. An unconsumed credit
does not produce a wrong-looking return. It produces a return that declares MORE
tax due than is owed, and it does so quietly, because a missing credit is
arithmetically indistinguishable from a taxpayer who had none.

A SIGNAL EXISTS, PARTIALLY, and the partition is not the one I expected.

The relation channel reports. `RelationPrefillSourceResolver` emits a
`source_issue` diagnostic naming the unresolved relation, which I observed live
rather than inferred: the no-history pole of the S02 regression asserts a
`source_issue` carrying `relation_id = "renta-2024-rel-130-pagos-fraccionados"`.
An operator who reads the diagnostics channel is told which credit did not
arrive. That covers the 62 `relation_prefill` slots.

One advisory watches the over-payment direction explicitly and by name.
`collect_prior_payment_not_deducted_diagnostics` in
`src/cadrumo/application/modelo/_prior_payment_advisory.py` fires when a
non-first trimestre has positive cumulative ingresos, casilla `05` resolved to
zero, and a real prior-trimestre filing exists in the observation store. Its own
docstring calls it "this prior over-payment advisory". It is wired into the live
calculate path through `collect_bucket_aggregation_advisory_diagnostics`.

But it is scoped to ONE modelo. `Modelo.M130` is hardcoded at four sites in that
module, twice as an early return and twice as the store scan's argument. Nothing
equivalent exists for any other modelo's prior-payment carry.

And its trigger is the presence of the evidence. It fires when a prior filing
EXISTS and the carry nonetheless resolved zero. That is the right trigger for the
defect it was built for, and it is exactly the wrong trigger for this campaign's
defect: where the history is structurally unreachable — the nine Sociedades slots,
or the modelo 100 revision cliff — no observation is stored, so the advisory's
precondition is never met and it stays silent. The watcher is blind to the case
where the credit is missing because it could never be fetched.

THE PREVIOUS-FILING CHANNEL HAS NO SIGNAL AT ALL, and this is the finding.

`PreviousFilingSourceResolver.resolve` returns a `CalculationSourceResolution`
carrying `binding_values` and `provenance`, and nothing else. It sets no
`diagnostics` and no `unresolved_binding_ids`. A `previous_filing` binding the
store cannot satisfy therefore produces literally nothing: no diagnostic row, no
unresolved id for the merge to propagate, no advisory. This is not a docstring's
intent that the code might exceed — `resolve_bindings_from_local_store` documents
that unsatisfied bindings are "skipped silently", and the resolver's return
statement is the confirmation that the documentation is accurate.

That silence covers all 17 `previous_filing` bindings, and the classification step
found that same 17 to be exactly the set the registry declares no treatment for.
The channel with no declared treatment is the channel with no diagnostic. Among
them: modelo 100's base liquidable negativa general carry, modelo 130's
cross-modelo prior-year net income, modelo 131's prior negative results on four
revisions, and modelo 720's three prior-year valuation baselines. Every one is a
relief or a baseline whose absence raises the declared figure.

So the plain answer the gate asks for: a signal exists for the relation channel
and for modelo 130's casilla `05`, and NO signal exists for the previous-filing
channel or for any structurally-unreachable carry. That is opened as its own row
rather than left as a note here.

## Verification

    rg -n "prior_payment_not_deducted|prior_payment_minoracion_not_captured|settlement_not_computed|official_box_unpopulated" src/cadrumo --glob '!**/tests/**' -g '*.py'

Every raise site of the four over-payment-adjacent reasons was read. Only
`prior_payment_not_deducted` is framed as an over-payment watcher by its own
module; `official_box_unpopulated` and `settlement_not_computed` are completeness
advisories that fire on a different question.

    rg -n "Modelo\.M[0-9]+" src/cadrumo/application/modelo/_prior_payment_advisory.py
    113:    for payload in repository.iter_modelo(Modelo.M130.value)
    166:    if modelo != Modelo.M130.value
    248:    if modelo != Modelo.M130.value
    255:    for payload in observation_repository.iter_modelo(Modelo.M130.value)

The modelo scoping is read off four literal sites rather than from the module
docstring, so "M130-only" is a property of the code and not of its description.

The claim that the previous-filing resolver emits nothing was read from its return
statement at `src/cadrumo/application/calculations/_multi_year.py:416`, which
constructs a `CalculationSourceResolution` with `resolver_id`, `owned_sources`,
`binding_values` and `provenance`, and no `diagnostics` or
`unresolved_binding_ids`. The only diagnostic-bearing path in that resolver is the
storage-degradation branch, which fires on an unreadable store rather than on an
unsatisfied binding.

The relation channel's diagnostic is not read from source but OBSERVED: the S02
regression's no-history test asserts the `source_issue` reason and the relation id
on a real run, and that test passes.

No pytest lane was run for this row itself and no production file was changed:
this row is an investigation.

## Notes

The gate requires that where no signal exists it opens its own row. It does, as
`P01.S10`, scoped to the previous-filing silence and to the structurally-
unreachable case the existing M130 watcher cannot see. It is deliberately NOT
scoped as "make the M130 advisory generic", because that would carry the M130
trigger — evidence present but unconsumed — into a case whose defining property is
that the evidence is absent, and it would then be silent for the same reason.

WHAT THIS DOES NOT ESTABLISH. It does not quantify the over-declaration. Knowing
that every unconsumed carry is a credit establishes the DIRECTION; the magnitude
depends on the taxpayer's actual prior filings and cannot be derived from the
registry. No claim is made about how much tax a real filer would overpay.

It also does not examine the verify gate or the export completeness gate, which
sit downstream of calculate and might refuse a draft the calculate path advised
nothing about. A missing credit does not leave a casilla blank — it leaves it
computed and wrong — so the completeness gates have nothing to bite on by
construction, but I did not run them to confirm that reasoning, and it is reasoning
rather than measurement. If the ruling depends on whether a downstream gate would
catch an over-declaration, it needs measuring first.
