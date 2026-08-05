---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:32abd5efa501845f04db673c152937de1e20e923890c07708a989f2eb87e734b'
step_id: 'S40'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---
# Prorate the Art. 81.2 guarderia increment per child by the intersection of the child age-eligible months, which are computable per month from the birth date, with the declared spend months where a monthly map exists, then bound by the mother qualifying-month count and by that child own non-subsidised spend, and for a child declaring only an annual total use the age-eligible month count as the proration basis rather than assuming twelve or refusing, disclosing the approximation as an advisory in both cases because the mother employment months are a count and their simultaneity cannot be verified until S44 gives them month identity

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/`
- `src/cadrumo/domain/contribuyente/family.py`
- `src/cadrumo/application/modelo/_profile_binding.py`
- `src/cadrumo/application/modelo/_calculate_input.py`

## Description

This is the third and final piece of the Step, the one that moves a live figure.
The two earlier pieces landed the per-child domain fold and the profile binding
that carries its result, each verified not to change any computed value; the
plan records that piecewise landing and its rationale.

- Point the Modelo 100 casilla 0613 formula at the resolved per-child increment
  binding, dropping the household spend total and the flat headcount-times-cap
  term it used to minimise over. The mother's cotizaciones ceiling is left
  untouched as the second term, because it is the subject of a separate open
  Step and folding it in would have decided that question by accident.
- Pin the proration clause of the manual in the formula's source citation, so a
  source that stopped stating it fails the registry load rather than leaving the
  claim unbacked.
- Add two calculate-path advisories on the typed notice channel: one for a zero
  increment that is zero only because the mother's qualifying months were never
  recorded, and one disclosing that the simultaneity intersection is an upper
  bound rather than a measurement.
- Retarget the annual-ceiling test helper from a formula literal to the registry
  parameter, the literal having been removed with the flat term, and delete the
  expression-walking helper that existed only to read it.
- Supply the new binding in the nineteen direct-engine test fixtures that
  assemble binding values by hand. These bypass the injector, and the engine
  refuses an unsupplied binding outright.

## Outcome

Casilla 0613 is prorated. Driven through the real CLI from `descendiente add` to
the calculated casilla, the manual's own worked case — a mother qualifying four
months against nursery paid in two — now yields the 166,67 the manual prints,
where the flat cap granted 1.000. That is an 833,33 over-grant closed on a
figure the authority states outright. The monthly-map case in the same suite
moves from 600 to 250 for the same reason: three post-birthday months earn three
twelfths of the ceiling, not the whole of it.

Both AEAT oracles reproduce end to end, 166,67 and 500,00, and neither is
hand-computed from the formula under test. The registry parameter is
cross-checked against the manual's arithmetic as a separate assertion, so a
drifted ceiling is named as such instead of surfacing as a wrong casilla.

Closing the over-grant opened its mirror, and that is absorbed here rather than
deferred. The mother's months default to zero and the record cannot distinguish
"declared none" from "never asked", so a taxpayer could declare real spend and
receive nothing with nothing saying why. The first advisory covers exactly that
state. The second carries the residual the Step anticipated: the guardería side
is a real month map but the mother's side is only a count, so the overlap taken
is the largest those two facts admit. It fires only where both spans are partial
and stays silent where either covers the year, since the intersection is then
exact and a disclosure would be noise. Both cases are pinned, the silent one as
a positive control.

Worst-case rendered advisory lengths were measured rather than assumed, against
the 512-character cap that now truncates instead of refusing: 427 and 482
characters at any household size. Both are asymptotic, because the only variable
segment names at most three descendants and counts the remainder.

## Notes

The brief scoped this as a swap of two terms for one. Three things it did not
anticipate were found and handled.

The mother's months are a term of the proration and were absent from three
existing end-to-end fixtures, which declared guardería spend and cotizaciones
but no employment months. Under the old flat cap that omission was invisible;
under the proration it collapses the increment to zero. The fixtures now declare
the months, which is also the more honest profile — a filer with cotizaciones on
record who worked no month of the year is a contradiction.

The annual ceiling had been read out of the formula as a literal by a test
helper. That literal is gone by design, since the application layer performs the
fold and cannot read a literal buried in a formula expression. The helper now
reads the registry parameter that replaced it.

Nineteen direct-engine fixtures needed the new binding supplied. They construct
binding values by hand rather than through the injector, and the engine refuses
an unsupplied binding, so this was a hard failure rather than a silent zero.

Two bindings are now consumed by nothing: the household guardería spend total
and the eligible-descendant count. They remain declared and resolvable, and
several tests still legitimately assert on them as profile-derived facts. They
are left in place rather than deleted, since removing them touches the derived
fact path that the spend-shape advisory reasons about and is wider than this
Step. Flagged for follow-up.

Three failures remain in the lanes run and none is owned here. Two in the binding
readiness suite fail inside registry load of a synthetic modelo 999 written to a
temporary directory, rejecting `label` as an extra input — the locale migration
moving labels off the schema. One in the XML dictionary export suite fails on
thousands-grouping ambiguity in an amount parser. Neither surface is touched by
this change, and the modelo 999 fixture cannot be reached by an edit to a modelo
100 formula.
