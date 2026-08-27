---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:4f0c1086d497297d279364aad2619734a96afb4e9e579e4ea6de33d5a72b3ecb'
related: []
---

# `tui-architecture` audit: the 2025 arrendamiento reduction is no longer computed

## CORRECTION — this audit's central claim is wrong

Casillas 0150 and 0613 are NOT a regression. They are a **deliberate, tested
deferral**, and this audit missed the guard that says so.

`domain/calculations/registry/tests/test_modelo_100_2025_semantic_boundaries.py`
states the contract in its own docstring:

> The 2025 declarations for casillas 0150, 0613, and 1481 are measured
> cross-revision divergences. They must not acquire a prior-year producer until
> their row-specific legal, input-contract, and independent-value evidence has
> been accepted. These tests exercise the loaded registry graph so an accidental
> formula, profile binding, or Modelo 131 relation cannot be added silently.

One of its tests asserts that the 2025 revision carries **no** guardería profile
binding at all. Another asserts 0150 and 0613 resolve to `manual` with no
formula and a producer trace carrying no formula, binding or relation.

So the absence of a producer is the *recorded state of an open question*, not an
omission. The reasoning below about direction and blast radius still describes
what a taxpayer experiences if the boxes are left blank, and the 2024-versus-2025
comparison is still accurate. What is wrong is the conclusion that this is a
defect to be fixed by porting the 2024 wiring.

Acting on that conclusion, the wiring was implemented and then reverted in
`8258892c64` after it broke 39 Modelo 100 registry tests, including the guards
above. The revert restores 449 passing.

What this audit should have done, and what the finding now is: the deferral is
real and its evidence bar is written down — row-specific legal, input-contract,
and independent-value evidence. Whether that bar has since been met for the
art. 23.2 arrendamiento reduction and the art. 81.2 guardería increment is the
open question, and it belongs to an owner. The method failure was mine: I did not
search for a guard on the rows before calling their state a defect.

## The finding

Modelo 100 casilla 0150 carries the LIRPF art. 23.2 reduction for arrendamiento
de vivienda -- the 50 / 60 / 70 / 90 percent tiers as amended by Ley 12/2023.

In the **2024** revision the engine computes it:

- `c0150` is `input_kind = computed`, bound to formula
  `renta-2024-capital-inmobiliario-reduccion-arrendamiento-vivienda-art-23-2`;
- that formula dispatches over binding
  `renta-2024-rental-reduccion-art-23-2-tier` (`bindings/0042-...`);
- the dispatch table reads all four `renta-2024-rental-reduccion-rate-tier-{50,60,70,90}`
  parameters.

In the **2025** revision, confirmed against the loaded snapshot, not the TOML alone:

- `c0150` is `input_kind = MANUAL`, `formula = None`;
- no formula targets casilla 0150 at all;
- the tier binding does not exist;
- all four `renta-2025-rental-reduccion-rate-tier-*` parameters ARE declared, and
  nothing in the revision or in production Python references them.

Both revisions compute the reduced net rental income identically as
`0154 = max(0149 - 0150 - 0151, 0152)`. So 0150 still feeds the chain -- it simply
has nothing to fill it.

## Direction, and why it is silent

If the operator leaves 0150 blank -- the natural state for a value the engine used
to derive -- the reduction is zero, `0154` equals the unreduced rendimiento, and
the landlord declares **more** rental income than the law requires. That is
over-payment of tax on 50 to 90 percent of net rental income.

`no-silent-under-declaration` flags "a manual base or result casilla with no
derivation and no guard" for the under-declaration direction. This is its mirror:
a manual RELIEF input with no derivation. The rule states the asymmetry plainly --
"nothing in it watches a taxpayer OVER-PAYING, and that direction produces valid
output, no refusal and no signal to the taxpayer" -- and this is an instance.

Nothing in the verify gate fires on it: a blank optional relief is a legitimate
zero for a taxpayer with no qualifying tenancy, and the gate cannot distinguish
that from a qualifying landlord whose reduction was never computed.

## Not incompleteness

The 2025 revision is mature and comparable to 2024 -- 2249 casillas, 192 formulas,
65 bindings against 2024's 2103 / 188 / 67. It is not a half-built revision that
has yet to reach this box. The rate parameters were authored for 2025; the binding
and formula that consume them were not.

## Remediation, for an owner

The 2024 shape is the template and is present in the tree: a
`rental-reduccion-art-23-2-tier` binding plus an `if_then_else` /
`lookup_parameter_by_entity_type` formula targeting 0150 over the four declared
tier parameters. Porting it is registry authoring against a live tax rule, and it
must be grounded and reviewed rather than copied mechanically -- the 2025 casilla
carries `rd-439-2007:art-13` alongside `ley-35-2006:art-23`, which the 2024 one
does not, so the two revisions do not describe the box identically and the
difference needs adjudication before wiring.

Do not close this by deleting the four unread parameters. That would remove the
evidence of the gap while leaving the taxpayer's reduction uncomputed.

## How it was found, and the probe's limits

A sweep for parameters no formula, binding, construct or expectation references
reported 130 candidates across 18 revisions. **That raw count is not
trustworthy**: production Python also resolves parameter ids by f-string
construction (`f"renta-{filing_year}-minimo-descendientes-{infix}{suffix}-{filing_year}"`
in `application/modelo/profile_binding.py`), so whole consumed families appear
unread to a TOML-only sweep. Adding a Python-side stem match reduced 200 to 130,
and the residue is still dominated by families that ARE reachable.

The families were therefore checked by hand. `minimo-ascendientes` and
`minimo-discapacidad` are referenced from casillas 0515-0518 across every revision
and are reachable. `rental-reduccion-rate-tier` was the outlier: 24 parameter
declarations across six years against exactly ONE downstream reference, in 2024
only. That asymmetry is what surfaced the regression.

The general class -- a rate parameter no formula reads -- remains only partly
swept, because a reliable sweep needs the Python resolution channel modelled
properly rather than by stem matching.

## The class, swept: three casillas, one revision transition

The rental reduction is not isolated. Sweeping every modelo with two or more
revisions -- 32 of them -- for casillas that were computed in the older revision
and are neither computed nor formula-targeted in the newer one, read from the
loaded snapshot:

**Exactly three, all Modelo 100, all in the 2024 -> 2025 transition, all reliefs.**

| casilla | concept | 2024 | 2025 |
|---|---|---|---|
| 0150 | art. 23.2 arrendamiento reduction | computed, tier binding, 4 rate parameters | manual; no formula, no binding; parameters left declared |
| 0611 | art. 81.1 deducción por maternidad | computed from `renta-2024-profile-deduccion-maternidad` | manual; no formula, no bindings, no parameter |
| 0613 | art. 81.2 incremento por gastos de guardería | computed from the guardería profile bindings | manual; no formula, no bindings, no parameter |

Modelo 100 2024 declares four maternidad/guardería profile bindings; the 2025
revision declares none of them, and none of the rental tier binding either.

The healthy direction dominates elsewhere: 44 casillas STARTED being computed
across the same comparisons, including a batch in 2023 -> 2024 that introduced
all three of these. So 2025 is not broadly regressing -- these three reliefs were
built in 2024 and not carried forward.

### 0611 and 0613 contradict an instruction the 2024 registry writes down

The 2024 formula for casilla 0611 carries this in its own comment:

> This registry leaf only carries that one derived legal result into the official
> casilla; it must not recreate or accept an operator-supplied 0611 total.

In 2025 casilla 0611 is precisely an operator-supplied total.

The 0613 comment records more that is lost. It describes a measured **833,33 EUR
over-grant** on the AEAT manual's own worked case, caused by a ceiling with no
month rule, and explains the art. 81.3 proration and per-child bound that fixed
it. That reasoning and its fix exist only in the 2024 fold. The 2025 revision has
no fold to carry it.

### Direction

All three reduce what the taxpayer pays. Left blank -- the natural state for a
box the engine used to fill -- the relief is simply absent and the taxpayer
over-pays. For 0611 and 0613 the amounts are material: art. 81.1 grants 100 EUR
per qualifying month capped at 1.200 EUR annually per child, and the guardería
increment adds up to a further per-child amount bounded by the mother's social
security contributions.

Nothing signals this. A blank optional relief is a legitimate zero for a taxpayer
with no children and no qualifying tenancy, and the verify gate cannot tell that
apart from a qualifying taxpayer whose relief was never computed.

## A false positive, and the probe correction it forced

The first sweep also reported Modelo 123 casilla 08 as a lost computation. It is
not. The 2024 revision renumbered the form from 8 boxes to 14: the old c08 was
`cuota_a_ingresar`, the new c08 is `retenciones_ingresos_a_cuenta`, and the
resultado formula still exists targeting a different casilla. The 2024 revision
has five formulas against the earlier two -- richer, not poorer.

Joining on casilla id across filing years is the exact hazard
`aeat-calculation-grounding` names: "never by casilla id across filing years --
ids renumber". The sweep now requires the semantic role to agree before treating
two ids as the same box, which drops the M123 row and leaves the three above.

Direction classification by role keyword also proved unreliable in that case:
`retenciones` reads as a relief on Modelo 100, where the taxpayer suffered them,
and as a liability on Modelo 123, where the withholder owes them. The direction
label is sound for the three M100 reliefs, which were each confirmed by reading
the casilla, and should not be trusted mechanically elsewhere.
