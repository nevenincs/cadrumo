---
tags:
  - '#adr'
  - '#descendant-profile-axis'
date: '2026-05-27'
modified: '2026-08-04'
body_hash: 'sha256:5b1e6f9f481fcac1b7245cb76cbf85e8d2c7198d8bfeccf76b5ebfd53e29f655'
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

- **Canonical schema.** Persisted `RentaFamilyProfile` records carry only the
  structured `descendientes` tuple. The retired scalar cannot be reconstructed
  without inventing per-descendant evidence, so it is rejected rather than
  migrated.
- **Test oracle sourcing.** Art. 58 thresholds (€2,400 / €2,700 / €4,000 /
  €4,500 / €3,000 disability supplement) are taken directly from the AEAT
  2024 registry parameters rather than hand-computed, satisfying the no-
  tautological-tests mandate.
- **Per-descendant NIF optionality.** `nif` is optional because minor
  dependants without a NIF are valid (under 14 years). Validation issues a
  warning advisory when `nif` is absent for a descendant over 14.

## D5 — Consequences

- `RentaFamilyProfile` exposes `descendientes: tuple[DescendantInfo, ...]` as
  its only descendant input; no scalar read path or migration validator exists.
- Registry bindings `renta-2024-profile-descendientes-count` and
  `renta-2024-profile-descendientes-minimos-aggregate` are added and wired
  into the M100 mínimo calculation chain.
- 42 tests cover oracle cases (AEAT 2024 parameters), roundtrip, anti-
  tautology, and `parse_descendiente_flag` helper.
- Locale keys for `DescendantInfo` fields and wizard prompts added across
  es/en/ca/hu.


## D6 — Amendment 2026-08-04: the axis under-describes the law, and this record is why

Added after a campaign corrected a live under-grant that traces to this document rather
than to the code implementing it. The implementation was faithful to the rule **as stated
here**; the rule was stated wrongly. That is recorded as the rationale rather than a
footnote, because a reader who sees only the corrections will re-derive the original from
the same source.

### D6.1 — Two citations in D1 are wrong, and one of them shipped a defect

**"Adoption supplement: Art. 67 grants an additional deduction in the year of adoption,
requiring `adoption_date`."** Both halves are wrong.

The supplement is **Art. 58.2**, not Art. 67. That misattribution propagated: it was found
and corrected across module docstrings, a registry formula comment, a schema description and
four locale catalogues — including one language where the wrong citation was spelled
differently, so a search for the original token would have missed it. Every one of those
sites was faithfully consistent with this record.

More consequentially, **"in the year of adoption" is a single period and the law grants
three.** Art. 58.2: *"En los supuestos de adopción o acogimiento, tanto preadoptivo como
permanente, dicho aumento se producirá, con independencia de la edad del menor, en el
período impositivo en que se inscriba en el Registro Civil y en los dos siguientes."*
Confirmed against the live authority, not only the bundled corpus.

Two further consequences follow from that sentence and neither is captured by D2.1. The
supplement is **age-independent** for these entries, so a child adopted above the ordinary
age threshold qualifies — the engine granted nothing for three years to exactly that
household. And the clause covers **adopción o acogimiento** while the assimilation clause
covers **tutela y acogimiento**, so the three placements are not interchangeable: acogimiento
takes the supplement, tutela does not.

**"Prorrata (Art. 58 §3)"** is also wrong. The prorrata is **Art. 61 norma 1ª**, and it is not
the 50%-per-contributor rule stated here — it prorates in equal parts among two **or more**
entitled contribuyentes, with a closer-degree rule and an exception that routes entitlement
to the next degree. The fixed-half reading is recorded as a known narrowing elsewhere.

**Art. 60 and Art. 81 are not re-verified by this amendment.** Two wrong citations in one
paragraph means the others are not safe to assume; they are flagged rather than corrected,
because sweeping beyond the amendment's scope is its own decision.

### D6.2 — The axis gains a relationship kind

`DescendantInfo` distinguishes **adopción**, **acogimiento** (preadoptivo o permanente), and
**tutela**. D2.1's field list cannot express the distinction the law makes, and the gap runs
both ways: an entitled acogimiento carer is under-granted, while the excluded tutela case is
reachable through the only date field the model offers. Neither direction is expressible
today, which is why this is a precondition for the remaining fixes rather than an
improvement to them.

### D6.3 — The entry date is a general entry-event date, not an adoption date

D2.1 names the field `adoption_date` and D1 justifies it by a single-year supplement. Both
readings are superseded.

The governing constraint is that the three-period window is **a cap, not a restart**: where
circumstances change — the authority's own example is an adoption following a fostering —
the increment continues for the remaining periods up to a maximum of three. So both events
can occur for the same descendant and the window spans them. A single field whose meaning
depends on the relationship kind therefore cannot express the rule, and an implementation
anchoring on whichever entry event it happens to hold would grant up to six years where the
law allows three.

The clause also anchors on Registro Civil inscription **or** the resolución judicial o
administrativa where inscription is not required, so the field's semantics are the entry
event, not the adoption specifically. A carer entitled under the acogimiento limb has no
correct place to record that date under D2.1.

### D6.4 — Month-level childcare spend is deferred, and this is a decision

The guardería increment extends into the period the child turns three, for spend incurred
after the birthday up to the month before the second infant-education cycle may begin — and
it survives even where the maternity deduction itself does not apply. The stored spend figure
is an annual total, so granting the full year would replace an under-grant with an
over-grant.

Deferred deliberately. It blocks the largest under-grant measured in this area by population,
since it reaches every household paying for childcare in the year their child turns three,
and the increment reduces the cuota directly. Recorded as a decision with what it blocks so
the omission is not read later as an oversight.

### D6.5 — The dependencia assimilation is retired, with its reasoning

The assimilation of dependencia to convivencia is retired rather than deferred. The statutory
carve-out excludes the judicial-anualidades case, which removes the one household shape that
would have made it common, and practice already treats temporary absence for study as
continuing convivencia. No reachable case could be constructed that is not better described
by another limb. The reasoning is preserved so a future reader can reopen it against
evidence rather than rediscover the question.

