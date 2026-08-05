---
tags:
  - '#adr'
  - '#descendant-profile-axis'
date: '2026-05-27'
modified: '2026-08-05'
body_hash: 'sha256:d51dde9f5a6cf9ee9a42eb759fb14dae75d43127e3ec24bef3d912673b8545a8'
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

**Scope of this amendment: it corrects what this record got wrong.** The forward decisions
it implies — the relationship-kind axis, the general entry-event date, the deferred
month-level spend, the retired dependencia assimilation — are decided in
`2026-08-04-minimo-descendientes-eligibility-deferred-descendant-axes-adr`, which is their
single home. They are summarised here only far enough to make the corrections legible.
Deliberately not restated in full: two records deciding the same thing is the drift this
campaign spent its day removing, and a design record is no more exempt from it than a
parser.

### D6.1 — Two citations in D1 are wrong, and one of them shipped a defect

**"Adoption supplement: Art. 67 grants an additional deduction in the year of adoption,
requiring `adoption_date`."** Both halves are wrong.

The supplement is **Art. 58.2**, not Art. 67 — which the corpus shows is *Cuota líquida
estatal*, an unrelated provision. That misattribution propagated: it was found and corrected
across module docstrings, a registry formula comment, a schema description and four locale
catalogues — including one language where the wrong citation was spelled differently, so a
search for the original token would have missed it. Every one of those sites was faithfully
consistent with this record.

More consequentially, **"in the year of adoption" is a single period and the law grants
three.** Art. 58.2: *"En los supuestos de adopción o acogimiento, tanto preadoptivo como
permanente, dicho aumento se producirá, con independencia de la edad del menor, en el
período impositivo en que se inscriba en el Registro Civil y en los dos siguientes."*
Confirmed against the live authority, not only the bundled corpus.

Two further consequences follow from that sentence and neither is captured by D2.1. The
supplement is **age-independent** for these entries, so a child adopted above the ordinary
age threshold qualifies — the engine granted nothing for three years to exactly that
household. And the clause covers **adopción o acogimiento** while the assimilation clause
covers **tutela y acogimiento**, so the three placements are not interchangeable.

**"Prorrata (Art. 58 §3)"** is wrong twice over, and the second way is sharper than the
first. Art. 58 has only apartados **1 and 2**, so §3 cites a subdivision that does not exist
— independently of being the wrong article. The prorrata is **Art. 61 norma 1ª**, which the
corpus confirms positively rather than by elimination: *partes iguales* appears in Art. 61
and nowhere in Art. 58. Nor is it the 50%-per-contributor rule stated here — it prorates in
equal parts among two **or more** entitled contribuyentes, with a closer-degree rule and an
exception routing entitlement to the next degree. The fixed-half reading is recorded as a
known narrowing elsewhere.

**The remaining citations and every figure were subsequently verified against the corpus and
all hold.** Art. 58's four tranche amounts, Art. 60's two disability figures and its article,
and Art. 81 for maternidad are correct as D1 states them. This check was deferred when the
amendment was first written, on the reasoning that two wrong citations in one paragraph made
the others unsafe to assume. That suspicion was right in direction and bounded in extent:
the two errors above are the only ones. Recorded explicitly because "not re-verified" reads
to a later author as "possibly also wrong", and no wider sweep is warranted.

### D6.2 — D2.1's field list is superseded, and where

The field list cannot express distinctions the law makes. `adoption_date` is adoption-named
and single, while the entitling clause spans adopción and acogimiento, anchors on Registro
Civil inscription **or** the resolución judicial where inscription is not required, and runs
as a **cap rather than a restart** — so both events can occur for one descendant and the
window spans them. A single field whose meaning depends on the relationship kind therefore
cannot express the rule, and anchoring on whichever event is held would grant up to six years
where the law allows three.

The replacement axis and its sequencing are decided in the record named above. What belongs
here is only the correction: **D2.1 is superseded on the entry-date field and on the absence
of a relationship kind**, and D1's single-year framing is why both looked sufficient.
