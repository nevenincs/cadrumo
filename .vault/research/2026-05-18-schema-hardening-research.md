---
tags:
  - '#research'
  - '#schema-hardening'
date: '2026-05-18'
modified: '2026-05-18'
related: []
---



# `schema-hardening` research: Semantic-atom drift across modelo registry schemas

## Motivation

The AEAT modelo registry under `src/aeat/_data/registry/aeat/modelos/`
declares 26 TOML schemas spanning ~172k lines and ~12,500 casillas.
Each schema is hand-authored against BOE and AEAT instruction sources,
then validated by the strict pydantic schema in
`src/aeat/domain/calculations/registry/_schema.py`. The schema enforces
identifier integrity, referential closure, and a narrow numeric-bounds
contract — but it does not enforce *semantic uniformity* across modelos.

The same domain concept (taxpayer NIF, payee name, fiscal year, postal
code, retenciones e ingresos a cuenta, IBAN) can be declared under
different casilla labels, different `data_type` values, different
`section` names, and different `constraints` shapes from one modelo to
the next. Because `data_type = "text"` accepts both a NIF and a free-text
title, and because `CasillaConstraints` carries only numeric bounds, the
registry has no structural surface where a modeller can express "this
casilla holds a NIF" in a way the schema can verify.

A six-agent discovery swarm surveyed all 26 modelo TOMLs across six
concept families (identity, naming, address, banking, fiscal-period,
monetary). This document consolidates their findings, surfaces the
recurring cross-cutting failures, and proposes a layered three-mechanism
intervention.

## Methodology

Six parallel sub-agents executed independent grep-and-tabulate passes
over the 26 modelo TOMLs. Each agent received a tight semantic scope,
catalogued every casilla, parameter, binding selector, and export header
field matching its family, and produced a markdown inventory plus a
short summary. Inventories were written to
`.vault-scratch/atom-inventory/` for reference; this document
consolidates the cross-cutting findings without duplicating the row-level
data. Each agent was instructed to read schemas only, write no source
files, and flag drift independently. The swarm output is treated as
discovery inventory — every numeric claim below traces back to a verified
hit in at least one agent's report.

## Findings

### F1 — The `data_type` Literal is too narrow to carry semantic intent

`CasillaDefinition.data_type` accepts a small closed set (`money`,
`decimal`, `text`, `boolean`, `integer`, `ratio`, and a handful of
others). It has no `"nif"`, `"name"`, `"country_code"`, `"year"`,
`"iban"`, `"postal_code"`, or `"date"` variant.

Concrete consequences:

- Every NIF, NIE, CIF, NIF-IVA, and foreign fiscal-ID casilla across
  the corpus carries `data_type = "text"`. The identity agent confirmed
  zero NIF fields declare a dedicated data type. The schema imposes no
  format, length, or check-digit constraint on any identifier.
- Every personal name and entity name field uses `data_type = "text"`.
  The naming agent reported 10 distinct semantic roles (taxpayer name,
  spouse name, entity legal name, etc.) all collapsed onto the same
  type as free-text titles and section headings.
- Country code is `text` with zero enforcement in every modelo with a
  country field (M100, M232, M349, M720). The schema has no
  `country_code` literal and no enumeration validator.
- Fiscal year is `data_type = "integer"` with no range guard. The
  schema has no `"year"` type.
- IBAN is `data_type = "text"` with no pattern, no length bound, no
  IBAN check-digit logic.

### F2 — `CasillaConstraints` supports only numeric bounds

The current constraints model carries `sign`, `min`, `max`, and a small
related set. It has no `pattern`, `min_length`, `max_length`, or `enum`
field. As a result, even when a modeller knows the legal contract on a
text field (IBAN must be 24 chars for ES, country must come from an
AEAT-supported list, postal code must be 5 digits), the schema cannot
carry the rule. The banking and address agents both independently
flagged this gap. Today an IBAN casilla accepts the empty string.

### F3 — Constraints are sparsely and inconsistently applied where they exist

The monetary-shape agent found that **31 of 12,520 casillas (0.25%)
carry any constraints at all**. All 31 use `sign = "non_negative"`;
`non_positive` never appears. Where the same semantic role appears in
multiple modelos, constraints application diverges:

- "Retenciones e ingresos a cuenta" appears in 15 modelos. Constrained
  with `non_negative` in 111, 115, 123. Unconstrained in 100, 130, 131,
  180, 190, 193.
- "Pago fraccionado" appears in 130, 131, 202. `non_negative` in 130
  and 202; missing in 131.
- Within M111, individual withholding line items are constrained but
  the total casilla 28 is not.

No registry-level rule explains the divergence. This is the strongest
single signal that the schema is not load-bearing for the consistency
properties a canonical-atom layer would enforce.

### Per-family severity summary

The full per-family inventories live in `.vault-scratch/atom-inventory/`.
The high-level severity matrix:

#### Identity (HIGH)

Nine distinct semantic roles: taxpayer NIF, spouse NIF, descendant NIF,
ascendant NIF, payee NIF, representative NIF, member/socio NIF,
intracomunitario counterpart NIF-IVA, foreign fiscal ID with id-type
discriminator. Key drift:

- Payee NIF is a first-class casilla in M180 and M184 but only a binding
  row-field in M190 and M193. The same semantic concept is invisible to
  any casilla-scanning surface for half the withholding-form corpus.
- M100/FEAC casillas 1974 and 1978 use a one-word `"NIF"` label with no
  subject qualifier. All other NIF casillas use `"NIF del <subject>"`
  patterns. Without consulting the source XSD the role is ambiguous.
- M100/2025 introduces new bound casillas `NIFDLG` and `DNIASDLG` for
  child and ascendant NIFs alongside the existing manual casillas
  0456..1757 with different label conventions and different sections —
  two structurally distinct identity fields for the same declarant
  subject.
- M720 declares `data_type` annotations inside binding selectors
  (`integer` for clave-de-identificacion, `text` for
  numero-de-identificacion-fiscal). These are validated only by the
  per-source typed selector model at snapshot build, not by
  `CasillaDefinition`. No casilla mirrors these foreign-identity atoms.

#### Naming (HIGH)

Ten distinct semantic roles. The polymorphic "person or entity name"
slot uses four different label phrasings across M180, M349, M720 — some
include `denominación`, some omit it. The same person (spouse,
descendant, ascendant) appears as a composite `apellidos y nombre` in
the identifying section AND as a bare `Nombre` (given name only) in
deduction-result sections of M100; no registry link enforces the split.
Filing modelos put names in `[[casillas]]`; informative modelos (M232,
M720) put names only in `[[bindings]]` selector rows. No unified naming
type bridges the two layers. Zero modelos declare a structured
person-vs-entity discriminator.

#### Address (HIGH)

Fifteen distinct semantic roles across 7 modelos (100, 131, 180, 232,
349, 720; 19 modelos carry no address content). Key drift:

- M232 collapses province code and country key into a single 2-char
  `text` field (`vinculada-N-provincia-pais`) with no discriminator. All
  other modelos keep these separate.
- Municipality is encoded three incompatible ways: M180 carries a
  parallel free-text name + 5-char text code; M100 deduction casillas
  carry only the 5-char code; M131 stores the municipality as a raw
  `integer` in a fichero-BOE binding with no casilla label.
- M720 stores the overseas entity/property address as a 164-char
  monolithic free-text blob; M180 decomposes the same real-world concept
  into 13 sub-fields (tipo-via, nombre-via, numero, escalera, piso,
  puerta, complemento, municipio, provincia, codigo-postal, …). Two
  irreconcilable structures for the same domain object.
- Country code is unconstrained `text` in every modelo. CCAA code
  appears explicitly as a casilla only from M100/2025 onwards; earlier
  revisions hide it inside `profile-tax-residence-ccaa` bindings.

#### Fiscal-period (HIGH)

Nine distinct semantic roles. Key drift:

- Period tokens differ: M202 uses `1P/2P/3P` for IS instalments; M369
  uses `EXT-1T..EXT-4T` for OSS imports; other quarterly modelos use
  `1T/2T/3T/4T`; ad-hoc modelos use `"AD-HOC"` or event names. No schema
  Literal constrains the value set.
- `decl.ejercicio` casillas are `data_type = "integer"` with no
  `constraints` block. No `"year"` type, no min/max enforcement.
- Devengo start date is `data_type = "date"` with `date_format =
  "ddmmaaaa"` in M232 export, but `data_type = "text"` with no format
  contract in M202 export — both are LIS modelos.
- Complementaria back-reference is decomposed in M349
  (`ejercicio-rectificado` + `periodo-rectificado`) but is an opaque
  receipt-number string (`previous_justificante`) in most other modelos
  with no year/period extraction.
- Year selector form is mutually exclusive between `years=[YYYY]` (M100,
  M131, M232) and `year_from=YYYY` (all others); the schema enforces
  uniqueness but tolerates either form, and the two encode different
  semantics (closed vs open-ended revision).

#### Monetary (MEDIUM-HIGH)

Casilla `data_type` histogram across the corpus: `money` 73.7% (9,232),
`text` 17.2% (2,149), `decimal` 4.7% (594), `boolean` 4.0%, `integer`
44, `ratio` 1. Parameter histogram: `bracket_table` 96, `ratio` 50,
`integer` 24, `money` 11. Casilla declarations carry no `unit` field
at all.

- `decimal` is used only in M100, M200, M202 (apparently for intermediate
  calculation results), but no schema rule encodes this distinction.
  Downstream filters that select `data_type == "money"` silently miss
  filing-grade amounts in those modelos.
- The single `ratio` casilla (M303 prorrata porcentaje) is semantically a
  0–100 percentage, but parameters use `ratio` for 0–1 fractions. No
  canonical type distinguishes the two.
- M180 `porcentaje-retencion` is `data_type = "text"` — a numeric rate
  stored as a fixed-width text field for BOE reasons, invisible to any
  numeric aggregation filter.
- Saldo negativo carry-forward in M130 and M131 is stored as a positive
  magnitude with `non_negative` constraint — an implicit sign convention
  not declared globally.

#### Banking (MEDIUM)

Forty-nine banking field hits, but concentrated: only 7 of 26 modelos
(M100, M111, M115, M123, M130, M131, M720) carry banking atoms; the
remaining 19 have none. Narrower blast radius than the other families.
Key drift:

- IBAN rectificación casillas 0687/0688 in M100/2020 renumbered to
  1780/1782/1783 in 2021–2023, then disappeared in 2024–2025 with no
  `deprecated` or `replaced_by` pointer in the schema.
- The same charge-account IBAN concept surfaces via three different
  registry layers: `header_key="iban"` in M111/M115/M123/M130 export
  layouts; a positional DID binding in M131; a casilla in M100. No
  shared type alias, no cross-surface referential link.
- BIC is present only in M720 (foreign asset declaration) and M100
  (foreign refund). The charge-account IBANs in M111, M115, M123, M130,
  M131 carry no BIC field and no schema rule that BIC must accompany
  non-ES IBANs.
- No `forma_de_pago`, `domiciliacion`, or `nrc` casilla exists in any
  modelo. Payment routing happens outside the calculable schema; no
  formula can gate IBAN-required validation on payment intent.

## Proposed Intervention

The findings converge on three layered mechanisms.

### Mechanism A — Extend the `data_type` Literal (type-erasure fix)

Add the missing semantic types to the `data_type` Literal in
`_schema.py`: `nif`, `nif_iva`, `name`, `country_code`, `ccaa_code`,
`province_code`, `postal_code`, `municipality_code`, `iban`, `bic`,
`year`, `period_code`, `date`. Back each with a dedicated pydantic
`Annotated` alias carrying a `BeforeValidator`:

- `nif` — Spanish NIF/NIE/CIF check-digit validator.
- `country_code` — ISO 3166-1 alpha-2 plus AEAT-supported extensions.
- `period_code` — Literal of `1T|2T|3T|4T|1P|2P|3P|4P|0A|01..12|EXT-NT`
  plus event names with documented carve-outs.
- `iban` — IBAN mod-97 check.
- `year` — bounded integer (e.g., `ge=2000`, `le=2099`) to match the
  existing `RegistrySnapshotRef.filing_year` bound.
- `date` — calendar date with a declared format.

Retrofit the 26 modelos to use the new types where applicable, leaving
true free-text labels on `text`.

### Mechanism B — Extend `CasillaConstraints` (constraint-expression fix)

Add `pattern` (regex), `min_length`, `max_length`, and `enum` slots to
`CasillaConstraints`. Wire them into the snapshot-build validator so a
casilla declaring `data_type = "text"` with `constraints.enum = [...]`
fails when a downstream value falls outside the enumeration. This
unlocks the modeller's intent even on legacy fields that cannot move to
a richer `data_type` immediately.

### Mechanism C — Inline `semantic_role` per casilla (cross-modelo identity fix)

Add an optional `semantic_role` slot on `CasillaDefinition`. A modeller
declares e.g. `semantic_role = "taxpayer_nif"` on every casilla that
carries that concept across the corpus. A snapshot-build validator
enforces:

1. **Intra-role consistency.** All casillas sharing a `semantic_role`
   must declare the same `data_type` and structurally compatible
   `constraints`. Divergent declarations fail snapshot build.
2. **Typo-twin warning.** A `semantic_role` value that appears on only
   one casilla in the entire corpus emits a warning at snapshot build.
   This is the only mitigation for inline-role spelling drift (e.g.
   `"taxpayer_nif"` vs `"taxpayer-nif"`); the warning surfaces likely
   typos without blocking load.
3. **Alias acceptance.** A casilla may declare
   `aliases = ["NIF declarante", "NIF del titular"]` carrying
   `legal_refs` and `source_refs`. The validator binds on semantic
   identity, not label-name uniformity, so legitimate BOE-derived label
   variants are preserved.

Inline declaration was chosen over a central catalogue or a pydantic
Literal: the modelling discipline already centralises authority through
`legal_refs` and `source_refs`, and the snapshot-validator pattern is
the established enforcement surface. The typo-twin warning is the
documented mitigation for the loss of central-catalogue typo detection.

## Severity ranking and rollout

| Mechanism | Risk | Highest-value atoms first |
|---|---|---|
| A — data_type extension | LOW (additive) | `nif`, `year`, `period_code`, `country_code`, `iban` |
| B — constraints expansion | LOW (additive) | `pattern` and `enum` are most-requested |
| C — semantic_role validator | MEDIUM (touches all 26 modelos) | taxpayer NIF, base imponible, retenciones e ingresos a cuenta |

Cold atoms (M720 monolithic domicilio, M232 province-or-country, M100
FEAC bare-NIF) should be captured as documented deviations via the
`aliases` mechanism in C rather than forced into canonical shape.

## Out of scope

- Banking-atom canonicalisation beyond MEDIUM-severity items (BIC, NRC,
  foreign IBAN).
- Restructuring the binding-vs-casilla decomposition split. Mechanism C
  applied across both layers covers this without restructuring.
- Cross-revision casilla deprecation tracking (M100 IBAN rectificación
  drop). Worth a follow-up but orthogonal to the atom layer.

## Next phase

Author the schema-hardening ADR consolidating mechanisms A, B, C with
hard-error failure mode at snapshot build and inline `semantic_role`
authoring.
