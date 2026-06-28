---
tags:
  - '#research'
  - '#modelo-720-prior-year-baseline'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
---



# `modelo-720-prior-year-baseline` research: `modelo 720 prior-year asset baseline and re-declaration trigger`

This research grounds the A3 mechanism of the multi-year-renta authorization
campaign: how Modelo 720 (declaración informativa de bienes y derechos situados
en el extranjero) carries a *genuine* cross-year dependency, and what the cheapest
registry-only mechanism is that exercises two distinct renta years for enrollment.

Modelo 720 is an informativa with no numeric calculation engine, so its
two-year evidence cannot be a calculation. It is, however, the one informativa
whose obligation logic is *intrinsically* multi-year: once a category of foreign
asset has been declared, it must be re-declared in a later year only if its
joint valuation grew by more than €20,000 over the last-declared baseline. That
prior-year baseline is the cross-year hook the campaign needs, and it is
statute-checkable, so it yields a stronger oracle than the typical structure/
provenance informativa test.

Every assertion below was re-verified against the live registry tree and the
in-repo legal corpus on 2026-06-02; the scratch design (`A2-A3-iva-research.md`)
was the starting point but is not trusted blindly — two of its specifics did
not survive verification and are corrected here.

## Findings

### Legal grounding (verified in the in-repo corpus)

The foreign-asset obligation and its thresholds are fully present in the
reviewed legal corpus under `src/aeat/_data/registry/aeat/legal/foreign-assets.toml`,
each slug carrying `review_status = "reviewed"`:

- `ley-58-2003:da-18` — Disposición adicional decimoctava LGT, the origin of the
  obligation to inform on foreign assets (introduced by `ley-7-2012:da-1`).
- `rd-1065-2007:art-42-bis` — cuentas en entidades financieras en el extranjero.
- `rd-1065-2007:art-42-ter` — valores, derechos, seguros y rentas en el extranjero.
- `rd-1065-2007:art-54-bis` — bienes inmuebles y derechos sobre inmuebles en el
  extranjero.
- `orden-hap-72-2013:art-1` — aprueba el Modelo 720 y sus diseños físicos/lógicos.
- `orden-hap-72-2013:art-2` — obligados; its `notes` records the €50.000 per-category
  initial-obligation threshold.
- `orden-hap-72-2013:art-7` — plazo (1 enero – 31 marzo del año siguiente),
  confirming the annual cadence and the N→N+1 chaining the baseline relies on.

The three asset categories of arts. 42-bis / 42-ter / 54-bis are a **closed
legal set** (cuentas / valores / inmuebles). This closure is the load-bearing
fact behind the cheap-path recommendation below.

The two thresholds:

- **Initial obligation (€50.000 per category):** declare a category only if its
  aggregate joint valuation strictly exceeds €50.000. Already centralised in code
  as `MODELO_720_REPORTING_THRESHOLD_EUR = Decimal("50000.00")` in
  `src/aeat/core/external_constants.py` (sibling of `M347_THRESHOLD_EUR`).
- **Re-declaration increment (€20.000 over last-declared baseline):** once a
  category has been declared, re-declare it in a later year only if its joint
  valuation rose more than €20.000 since the last declaration (arts. 42-bis.5 /
  42-ter.5 / 54-bis.7). **This €20.000 constant is NOT yet present in the legal
  corpus or in `external_constants.py`** — its addition is part of this mechanism's
  scope, not a pre-existing asset. The constant should land beside
  `MODELO_720_REPORTING_THRESHOLD_EUR` as
  `MODELO_720_REDECLARATION_DELTA_EUR = Decimal("20000.00")`.

### Fichero layout (verified against the live bindings)

The fixed-width fichero already anticipates prior-year chaining; **no format
change is required.** Verified against
`src/aeat/_data/registry/aeat/modelos/720/.../bindings/0001-bindings.toml`:

- `type_1` offset 123–135 (len 13) `numero-identificativo-de-la-declaracion-anterior`
  — the prior-declaration link; chaining is anticipated in the layout.
- `type_1` offset 121–122 (len 2) `declaracion-complementaria-o-sustitutiva`.
- `type_1` offset 145–162 (len 18, text) `suma-total-de-valoracion-1-saldo-o-valor-a-31-de-diciembre-s`
  — the declaration-level total of valuation-1 across all asset records.
- `type_2` offset 102 (len 1, text) `clave-tipo-de-bien-o-derecho` — per-record
  asset-class key (C/V/I/S/B).
- `type_2` offset 103 (len 1) `subclave-de-bien-o-derecho`.
- `type_2` offset 432–446 (len 15, text) `valoracion-1-saldo-o-valor-a-31-de-diciembre`
  — the per-record valuation at 31-Dec.

All `type_1`/`type_2` bindings in `0001-bindings.toml` are `source = "manual_input"`.
The row-level aggregates in `0002-bindings.toml` are `source = "foreign_asset"`
with `selector.grouping = "per_foreign_asset"` and `record = "bien"`.

### Two scratch specifics that did NOT survive verification

1. **`grouping = "per_foreign_asset_class"` does not exist.** The scratch design
   proposed a `previous_filing` binding with `grouping = "per_foreign_asset_class"`.
   Two independent facts refute this:
   - `RowSetGroupingKind` (`src/aeat/core/aggregation.py`) declares only
     `FOREIGN_ASSET = "foreign_asset"` for this domain; there is no per-class
     grouping member. `src/aeat/application/calculations/_row_set_assembly.py`
     maps `"per_foreign_asset" -> RowSetGroupingKind.FOREIGN_ASSET` and
     `"per_atribucion_member" -> RowSetGroupingKind.ATRIBUCION`, and nothing else
     for foreign assets.
   - The `previous_filing` selector model `_PreviousModeloSelector`
     (`src/aeat/domain/calculations/registry/_bindings.py`) is
     `extra="forbid"` and **declares no `grouping` key at all.** A `grouping`
     entry on a `previous_filing` selector would fail to construct.

   Conclusion: the dynamic per-class grouping is not constructable. This *confirms*
   the cheap-path recommendation rather than contradicting it.

2. **`source_output` vs `source_casillas`.** The scratch design wrote the baseline
   selector with both a singular `source_output = "type_1.suma-total-…"` *and* a
   `grouping` key. The verified selector supports exactly two mutually-exclusive
   source shapes (`_validate_source_spec`): plural `source_casillas` (tuple,
   for `op = "sum"` aggregation) OR singular `source_output` (one casilla,
   for `op = "copy"`). The baseline is a one-value copy of a prior-year total,
   so the singular `source_output` + `op = "copy"` shape is correct — matching the
   precedent `modelo-390-prev-303-compensacion-ultimo-periodo` binding, which uses
   `period = "4T"` + `source_casillas = [...]` + `aggregation = { op = "copy" }`.

### The cross-year mechanism (verified)

The prior-year hook is `filing_year_delta`. The resolver computes
`expected_year = filing_year + selector.filing_year_delta + period_year_delta`
(`resolve_previous_filing_binding_values` / `previous_filing_observation_requirements`
in `_bindings.py`), so `filing_year_delta = -1` resolves last year's filing.
`filing_year_delta = -1` is already exercised in `test_selector_shape.py`, and the
canonical prior-year copy precedent is the Modelo 130
`_previous_year_net_income_binding` (`test_formula_runtime.py`), which copies the
prior ejercicio's net income with a year-delta cap. Modelo 720 is annual
(`revision.toml`: `period_selector = { year_from = 2012, periods = ["0A"] }`;
`manifest.toml`: `cadence = "annual"`), so the baseline anchors on `period = "0A"`.

### Re-declaration trigger: a genuinely new semantic

The re-declaration trigger is **not** expressible by any existing verification
predicate operator. `KNOWN_VERIFICATION_PREDICATE_OPERATORS` is the closed set
`{advisory_when_ratio_ge, all_nonzero, any_nonzero, cap_le_when_positive,
implies_nonzero, profile_field_required}`. The M200 precedent uses
`implies_nonzero(["00501", "DP200014:00552"])` with `finding_kind = "ADVISORY"` —
a *single-filing* "antecedent positive ⇒ consequent non-zero" shape. The 720
trigger is different: it compares a **current-year per-category total** against a
**prior-year per-category baseline binding value** and tests whether the delta
exceeds a fixed €20.000 statutory threshold, firing only when the category grew
> €20.000 yet is absent from the current declaration.

That "delta over a euro threshold against a prior-year baseline, advisory when the
grown category is absent" shape has no existing operator. The ADR must therefore
decide between (a) authoring a new predicate operator, or (b) the cheaper
registry-only formulation, discussed below.

### Recommended mechanism (cheapest, zero schema change)

Because the asset categories are a closed legal set, the baseline does not need a
dynamic per-class grouping. Author **three fixed per-category `previous_filing`
baseline bindings** (cuentas, valores, inmuebles), each with a distinct
`source_output` naming that category's prior-year per-class total,
`filing_year_delta = -1`, `period = "0A"`, `aggregation = { op = "copy" }`, and
the per-category legal_refs. This is pure registry authoring with **zero schema
change** and avoids the non-existent per-class grouping entirely.

For the re-declaration trigger, the lowest-risk advisory formulation mirrors the
M200 advisory in spirit: surface an **ADVISORY** finding (never blocking, per the
`no-silent-under-declaration` discipline) when a category's prior-year baseline is
present, the category grew more than €20.000, and the category is absent from the
current declaration. Because no existing predicate operator expresses the
prior-year-baseline delta, the ADR's decision point is whether to add one
operator (`redeclaration_required_when_growth_exceeds`, advisory) or to model the
delta as a derived casilla/formula and gate it with an existing operator. Either
way it stays ADVISORY: growth ≤ €20.000 legitimately need not re-declare, so a
blocking rule would refuse legal filings.

### Two-year enrollment scenario (statute-grounded oracle)

- **Year N:** declare cuentas €60.000 and valores €55.000 (both > €50.000 →
  obligated). Inmuebles absent.
- **Year N+1:** cuentas €85.000 (+€25.000 > €20.000 → MUST re-declare) and
  valores €65.000 (+€10.000 ≤ €20.000 → re-declaration NOT required).

Invariants: the three per-category baselines auto-resolve N→N+1 via
`filing_year_delta = -1`; the re-declaration advisory fires for cuentas and NOT
for valores. The €20.000 / €50.000 thresholds are **statute-checkable**, so the
test is a genuine threshold-logic oracle, not a tautological structure check —
satisfying `no-tautological-calculation-tests`. The enrollment test clones the
real-adapter pattern of `test_modelo_130_carry_forward_continuity.py` (real
SQLite, real `ValidatedRegistryAuthority`, real previous-filing resolver, no
mocks), and registers two distinct renta years with the authorization recorder,
satisfying the foundational gate's un-fakeable two-year contract.

### Why this mechanism lands first

Among the campaign's mechanism ADRs, A3 is the lowest risk: it is pure
registry-authoring plus one new euro constant and (at most) one advisory predicate
operator. It needs no schema extension (unlike A2's member-grouping axis) and no
engine build (unlike the 714/151/721/210 modelos). Its oracle is the strongest of
the informativa set because the thresholds are statutory. It should land first to
de-risk the campaign's mechanism track.
