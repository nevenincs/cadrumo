---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:f00701256992a9c1912349e1aa496d08b1d9e28b04eba404bce02590cb84348c'
related: []
---

# `tui-architecture` audit: the 2025 arrendamiento reduction is no longer computed

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
