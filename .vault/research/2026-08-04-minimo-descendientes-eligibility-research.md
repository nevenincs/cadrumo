---
tags:
  - '#research'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:24d2d7db0fb3af23d540f1353f7665ba25fb331220858de03647d078fc47eaf3'
related:
  - "[[2026-07-01-modelo-100-minimo-descendientes-engine-adr]]"
  - "[[2026-05-27-descendant-profile-axis-adr]]"
---

# `minimo-descendientes-eligibility` research: `Art. 58/61 LIRPF eligibility conditions unmodelled in the mínimo por descendientes derivation`

The Modelo 100 mínimo por descendientes engine derives casillas `0513` (estatal) and
`0514` (autonómico) from per-descendant facts plus registry Art. 58 tranche parameters.
The question this research answers is whether that derivation is complete against the
law it cites. It is not: four conditions the bundled LIRPF corpus states are absent from
the eligibility predicate, and one of them mis-states the mínimo for an ordinary
two-parent household. The matter is urgent because the only correction channel today is
an operator override of the derived aggregate, and a concurrent campaign
(`profile-derived-selectors`) is designed to close that channel.

## Findings

### The eligibility predicate tests three conditions; the law states seven

`RentaFamilyProfile` ranks descendants through `DescendantInfo.is_eligible_ordinary`
(`src/cadrumo/domain/contribuyente/family.py:176-186`), which returns true when the
descendant cohabits AND (carries any `discapacidad_grado > 0` OR is under 25 at
year-end). `minimo_descendientes_estatal` (`family.py:390-447`) multiplies each eligible
descendant's birth-order tranche by a prorrata factor and sums.

No other eligibility filter exists. `rg` for the Art. 58.1 rentas threshold across
`src/cadrumo/domain/contribuyente/` returns no `8000` / `8_000` occurrence, and the 2024
registry parameter set (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/parameters/`,
files `0033`-`0037`) declares only the four birth-order tranches and the menor-tres
supplement — no rentas-limit parameter exists to be consumed.

### Art. 61 norma 1ª: proration is keyed to shared custody, but the law keys it to entitlement

The bundled corpus states the rule without reference to custody arrangements:

> Cuando dos o más contribuyentes tengan derecho a la aplicación del mínimo por
> descendientes, ascendientes o discapacidad, respecto de los mismos ascendientes o
> descendientes, su importe se prorrateará entre ellos por partes iguales.

The trigger is *entitlement*. `custodia_compartida_prorrata_factor`
(`family.py:379-388`) returns the 0.5 factor only when `descendant.custodia_compartida`
is true, and `minimo_descendientes_estatal:446` applies that factor alone. Two cohabiting
parents, both entitled, each filing an individual declaración therefore each take the
full mínimo rather than half.

This is the largest of the four gaps by population and it moves in the
under-declaration direction: an inflated mínimo reduces the base and the tax. Individual
versus conjunta is a routine filing choice, so the affected shape is ordinary rather
than exceptional. The authoring intent is visible and narrow — `family.py:416-421`
discusses Art. 61's temporal rules and scopes them out deliberately, so norma 1ª was
read as the custodia-compartida rule rather than the general entitlement rule.

### Art. 58.1 rentas cap and Art. 61 norma 2ª own-return exclusion are absent inputs

The corpus states the cap as "rentas anuales, excluidas las exentas, superiores a 8.000
euros" and the own-return condition at the 1.800 euro figure. Neither is expressible:
`DescendantInfo` (`family.py:83-120`) declares `birth_date`, `adoption_date`,
`discapacidad_grado`, `convive_con_contribuyente`, `custodia_compartida`,
`meses_madre_trabajo_2024`, `gastos_guarderia_euros` and `nif`. There is no income field
and no own-declaración flag, so no predicate can consult them. Both gaps also
over-declare the mínimo.

### One predicate, three consuming surfaces, two directions of error

`is_eligible_ordinary` feeds the estatal aggregate, the autonómico aggregate, and the
anualidades Art. 64/75 eligibility flag. The first two share the defect and its
direction; Madrid's divergent tranche table changes amounts, not eligibility
(`src/cadrumo/application/modelo/_profile_binding.py:403-432`).

The anualidades flag inverts it. The binding is
`renta-2024-profile-anualidades-sin-minimo-descendientes` — true when the payer has NO
mínimo right. A descendant with rentas above the cap generates no mínimo, so the payer
is legally sin derecho and the separate Art. 63 escala should apply; the injector counts
that descendant eligible (`_profile_binding.py:471-475`) and the flag reads false,
denying the régimen. Splitting the base into two bracket lookups is generally
favourable, so denying it over-taxes. One predicate fix corrects all three.

### The Art. 64 base comparison IS enforced; the régimen predicate is sound

The corpus conditions the separate escala on "cuando el importe de aquellas sea inferior
a la base liquidable general". Formula
`0148-renta-2024-cuota-escala-estatal-sobre-base-liquidable-general.toml` enforces it as
a nested short-circuit: `greater_than(0527, 0)` then `less_than(0527, 0505)` then the
profile eligibility binding, falling through to the ordinary `escala(0505)` otherwise.
The condition is implemented in the registry formula rather than the profile flag, which
is the correct home. This line of inquiry closed as a negative result: no defect.

### The correction channel exists today and is scheduled for removal

The derived aggregates are injected at calculate time and the injectors skip keys
already present (`_profile_binding.py:388,405,413`), so an operator-stored fact at
`renta_family.descendientes_minimos_aggregate_{year}` overrides the computation. That is
the only way a filer can currently reach a correct figure in any of the four scenarios.
The `profile-derived-selectors` campaign refuses operator writes to those paths, so the
sequencing constraint is hard: the derivation must be correct before the override closes,
or a correctable over-declaration becomes uncorrectable.

### Option space

Modelling the missing conditions requires operator-supplied facts that no per-descendant
observable can derive — the rentas figure and the own-return flag are external, and
norma 1ª proration depends on whether another entitled filer is also claiming. Two
shapes present: per-descendant factual inputs from which the predicate computes, or a
per-descendant applicability override the predicate honours. The evidence favours
factual inputs for the two threshold conditions (they are observable figures with a
legal test) and an applicability override for norma 1ª proration (the co-filer's
behaviour is not a fact about the descendant). The ADR must settle the split, the
default value of any override, and whether a default that preserves today's behaviour
needs an accompanying advisory.

### Not investigated

Art. 61 norma 4ª (mid-year death, fixed 2.400 euro amount) is confirmed unmodelled and
is not costed here. The Art. 58.1 asimilación of tutela/acogimiento, and of dependencia
to convivencia, is likewise unmodelled and under-grants rather than over-grants. Whether
revisions 2020-2023 and 2025 share the defect was not probed per-revision; the predicate
is revision-independent so they are expected to, but this is inference rather than
measurement.

The mínimo por ascendientes was audited and is a clean negative for this campaign's
scope. Casilla `0515` (`.../revisions/2024/casillas/0497-0515.toml`) declares no
`input_kind` and no binding, and no formula targets it — it appears only as an input to
the mínimo personal y familiar sum in
`0072-renta-2024-minimo-personal-y-familiar-estatal.toml`. It is therefore a bare manual
input, so there is no derivation to carry an incomplete predicate. No `AscendantInfo`
model and no ascendant eligibility method exist in `src/cadrumo/domain/contribuyente/family.py`.

That is not the same as sound. The ascendientes axis carries the same partially-scaffolded
shape the descendientes axis had before its engine landed: the profile schema declares a
`renta_family.ascendants` array with birth date, disability grade, cohabiting-descendant
count and death date, and a binding `renta-2024-family-ascendant-cohabiting-descendant-count`
exists and resolves to nothing on a thin profile. A future ascendientes engine would face
the identical eligibility question (Art. 59 conditions the mínimo on age, cohabitation and
a rentas ceiling) and should model the predicate completely at the outset rather than
repeating the incomplete-predicate sequence this research documents.

## Sources

- `src/cadrumo/domain/contribuyente/family.py:83-120` — `DescendantInfo` field set
- `src/cadrumo/domain/contribuyente/family.py:176-186` — `is_eligible_ordinary`
- `src/cadrumo/domain/contribuyente/family.py:379-388` — `custodia_compartida_prorrata_factor`
- `src/cadrumo/domain/contribuyente/family.py:390-447` — `minimo_descendientes_estatal`
- `src/cadrumo/application/modelo/_profile_binding.py:388,405,413` — injector skip-if-present guards
- `src/cadrumo/application/modelo/_profile_binding.py:403-432` — estatal and autonómico injection
- `src/cadrumo/application/modelo/_profile_binding.py:471-475` — anualidades eligibility derivation
- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html` — Arts. 58, 61, 64 consolidated text
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/parameters/0033-0037` — tranche parameters
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0148-renta-2024-cuota-escala-estatal-sobre-base-liquidable-general.toml` — Art. 64 base comparison
