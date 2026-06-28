---
tags:
  - '#adr'
  - '#descendant-profile-axis'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-04-21-modelo-100-renta-adr]]"
  - "[[2026-05-08-renta-cuota-integra-state-scale-adr]]"
  - '[[2026-06-04-descendant-profile-axis-research]]'
---


# `descendant-profile-axis` adr: Descendant profile axis | (**status:** `accepted`)

## D1 — Context

Three persona audit rounds exposed a gap in the M100 mínimo personal y
familiar calculation: Inés (round-23, adopted daughter born 2010), Yara
(round-14, two biological children + maternidad deduction), and Marcos
(round-21, married). The LIRPF Arts. 57–60 mínimo por descendientes
computation requires per-descendant data that was unavailable in
`RentaFamilyProfile`.

Prior to this ADR `RentaFamilyProfile` carried only a count
`hijos_menores_25: int` with no structured per-descendant record. The count
was insufficient to compute:

- Age-based thresholds: Art. 58 grants €2,400 for the first descendant,
  €2,700 for the second, €4,000 for the third, and €4,500 for the fourth+.
- Disability supplement: Art. 60 grants €3,000 (grado 33-64%) or €9,000
  (grado 65%+) per descendant with a recognised disability.
- Adoption supplement: Art. 67 grants an additional deduction in the year
  of adoption, requiring `adoption_date`.
- Prorrata (Art. 58 §3): when a descendant does not live with both parents,
  the mínimo is prorated 50% per contributor.
- Maternidad deduction (Art. 81): conditional on `convive_con_contribuyente`.

The previous count-only representation meant these casillas were unreachable
for any persona with more than zero children.

## D2 — Decision

### D2.1 — Introduce `DescendantInfo` frozen pydantic model

Add `DescendantInfo` as a `strict=True`, `frozen=True` pydantic model with
fields: `birth_date: date`, `adoption_date: date | None`,
`discapacidad_grado: Literal[0, 33, 65]`,
`convive_con_contribuyente: bool`, and `nif: str | None`.

Model validators enforce:
- `adoption_date >= birth_date` when `adoption_date` is set.
- `adoption_date <= today` (no future adoption dates).

### D2.2 — Replace count with tuple on `RentaFamilyProfile`

Replace `hijos_menores_25: int` with
`descendientes: tuple[DescendantInfo, ...]` on `RentaFamilyProfile`.
The count remains available as a derived `@property` for casillas that need
the scalar.

### D2.3 — Registry bindings for Art. 58 mínimo

Add two registry bindings under `renta-2024`:
`renta-2024-profile-descendientes-count` (scalar count projection) and
`renta-2024-profile-descendientes-minimos-aggregate` (Art. 58 stepped
aggregate: €2,400 + €2,700 + €4,000 + €4,500 per ordered descendant, capped
at the AEAT 2024 table parameters).

## D3 — Alternatives considered

**Alternative A: flat per-descendant fields (hijo_1_*, hijo_2_*, …).** A flat
schema with numbered field groups was considered. Rejected: it caps the
descendant count at authoring time, creates a sparse field set for families
with fewer than the maximum, and produces a schema explosion that does not
reflect the list semantics of Art. 58.

**Alternative B: `list[DescendantInfo]` instead of `tuple`.** A mutable list
was considered. Rejected: `RentaFamilyProfile` is a frozen pydantic model and
`tuple` is the idiomatic immutable sequence type. `tuple` also provides
Pydantic v2's strict homogeneous sequence validation.

**Alternative C: store only the count + disability flag.** Retaining a count
plus a simple `tiene_hijos_discapacitados: bool` was considered as a minimal
delta. Rejected: it is insufficient for prorrata, adoption supplement, and
the per-child disability grade required by Art. 60.

## D4 — Trade-offs

- **Schema migration.** Existing persisted `RentaFamilyProfile` records that
  carry `hijos_menores_25` as a scalar integer need a migration shim to
  construct an equivalent `descendientes` tuple. This is handled by a
  `model_validator(mode="before")` that converts the legacy scalar to an
  equivalent tuple of generic `DescendantInfo` records with
  `discapacidad_grado=0` and `convive_con_contribuyente=True`.
- **Test oracle sourcing.** Art. 58 thresholds (€2,400 / €2,700 / €4,000 /
  €4,500 / €3,000 disability supplement) are taken directly from the AEAT
  2024 registry parameters rather than hand-computed, satisfying the no-
  tautological-tests mandate.
- **Per-descendant NIF optionality.** `nif` is optional because minor
  dependants without a NIF are valid (under 14 years). Validation issues a
  warning advisory when `nif` is absent for a descendant over 14.

## D5 — Consequences

- `RentaFamilyProfile` gains `descendientes: tuple[DescendantInfo, ...]`.
  Legacy `hijos_menores_25` is consumed in a `model_validator(mode="before")`
  and does not appear in the schema surface.
- Registry bindings `renta-2024-profile-descendientes-count` and
  `renta-2024-profile-descendientes-minimos-aggregate` are added and wired
  into the M100 mínimo calculation chain.
- 42 tests cover oracle cases (AEAT 2024 parameters), roundtrip, anti-
  tautology, and `parse_descendiente_flag` helper.
- Locale keys for `DescendantInfo` fields and wizard prompts added across
  es/en/ca/hu.
