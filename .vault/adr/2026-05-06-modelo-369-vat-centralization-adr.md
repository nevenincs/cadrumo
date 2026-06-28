---
tags:
  - '#adr'
  - '#modelo-369-vat-centralization'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-modelo-369-vat-centralization-audit]]'
  - '[[2026-05-06-modelo-369-vat-centralization-research]]'
  - '[[2026-05-06-vat-rate-shadow-sweep-audit]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `modelo-369-vat-centralization` adr: `oss-ioss-regime-substrate-and-ledger-binding-shape` | (**status:** `proposed`)

> **PARTIALLY-SUPERSEDED 2026-05-19**: The Value-Added Tax direction in this ADR is reversed: Spanish stems are authoritative for tax-domain identifiers and domain/vat migrates into domain/iva. The OSS/IOSS regime taxonomy, classifier-rule shape, ledger_oss_aggregation binding source, Modelo 369 single-modelo three-revisions shape, teardown sequencing, and LIVA grounding remain in force. Module-path mentions (aeat.domain.vat, domain/financial/vat) and the spelling of IvaRate, VatRateKind rename per the cluster ledger when the IVA migration lands.
> See `2026-05-19-spanish-stem-terminology-authority-adr` for the canonical
> rename ledger and Spanish-stem terminology authority.


## Review State

This ADR is proposed for review. It builds on the
calculation-truth-registry parent ADR by deciding the substrate and
binding mechanics for the first registry-grade ledger-driven modelo
(369). It is conditional on the two-loop audit and the research doc
listed in `related:` above; future review notes should be added against
the substrate decision, the regime taxonomy, the ledger binding shape,
the teardown plan, and the corpus prerequisite list.

The parent calculation-truth-registry ADR remains authoritative for
everything not redecided here: TOML-as-truth, registry validator
gates, snapshot immutability, the forbidden remote-state surfaces,
and the ban on filing-grade legal values in Python modules. This ADR
extends those decisions with the specific shape that Modelo 369 OSS /
IOSS work requires.

## Problem Statement

Modelo 369 is the first registry-grade modelo whose calculations and
filing values derive from the local ledger plus deductible-expense
surfaces rather than from manually entered casillas, fixed-formula
chains, or summaries of other modelos. The user has flagged that
Modelo 369 raises VAT concepts the codebase has not yet tackled and
has stipulated that any 369 work must rest on a centralized,
audited, non-shadowed VAT substrate.

The audit and research loops surfaced four classes of gap that block
Modelo 369 work:

- The closed VAT taxonomy in `aeat.domain.vat` does not enumerate the
  three OSS / IOSS Esquemas (Exterior, Unión, Importación) and does
  not include IOSS-specific transaction kinds, classifier rules, or a
  per-regime deductibility predicate.
- No committed modelo registry currently consumes the VAT substrate.
  Modelo 369 will therefore have to introduce the ledger ↔ modelo
  binding mechanism for VAT-driven aggregations, since the existing
  `manual_input` and `previous_filing` binding sources do not cover
  ledger-derived rate-keyed aggregation.
- Modelo 369's filing cadence is regime-conditional (monthly for
  Importación, quarterly for Exterior and Unión). The current modelo
  registry schema declares one cadence per revision, so the modelo
  shape must be decided.
- The codebase still carries hardcoded filing-grade rate values
  outside the registry: `aeat.domain.invoices._enums.IvaRate`
  hardcodes Spanish IVA percentages, and
  `aeat.domain.rental._aggregates` hardcodes the LIRPF article 85
  imputación rates. These shadows must come down before Modelo 369
  binds to the substrate, otherwise the substrate's authority is
  defeated by the parallel Python rate sources.

## Decision

This ADR proposes the following decisions.

1. Extend `aeat.domain.vat` in place rather than creating a sibling
   `aeat.domain.oss/` module. The substrate already centralizes Member
   States, rate windows, transaction kinds, residency axes, and the
   classifier; the OSS / IOSS additions are taxonomy and rule-set
   extensions that the existing schema absorbs cleanly.
2. Add a closed `OssIossRegime` `StrEnum` with members
   `EXTERNAL_SCHEME`, `UNION_SCHEME`, and `IMPORT_SCHEME`. Each member
   carries a docstring citing the LIVA article range that establishes
   it. LIVA art. 163 septiesdecies provides the definitions common
   to all three regimes (declaraciones-liquidaciones periódicas,
   Estado miembro de consumo, Estado miembro de identificación). The
   regime-scoped ranges are: Exterior (régimen no establecidos en la
   Comunidad): art. 163 octiesdecies through 163 vicies; Unión
   (régimen establecidos en la Comunidad pero no en el Estado
   miembro de consumo): art. 163 unvicies through 163 quatervicies;
   Importación (régimen ventas a distancia de bienes importados):
   art. 163 quinvicies through 163 octovicies.
3. Introduce a regime ↔ periodicity mapping inside the substrate that
   declares `EXTERNAL_SCHEME` and `UNION_SCHEME` as quarterly and
   `IMPORT_SCHEME` as monthly. The mapping is consumed by the
   modelo registry to validate the Modelo 369 cadence selection and
   by the deadline-window resolver to compute filing windows. Per
   HAC/610/2021 art. 2 letters (c) and (d), the Importación regime
   has two filer roles — direct sujeto pasivo and intermediario
   establecido en TAI acting on behalf of others — both filing
   monthly; the intermediario role files one autoliquidación per
   month per represented empresario. The substrate captures the role
   distinction with a separate `IossFilerRole` axis (`DIRECT` /
   `INTERMEDIARIO`) that does not affect the regime ↔ periodicity
   mapping but flows into Modelo 369 binding selectors so per-empresario
   declarations can be aggregated correctly.
4. Extend `TransactionKind` with regime-aware markers:
   `OSS_UNION_GOODS_DISTANCE_SALE`,
   `OSS_UNION_GOODS_INTERFACE_FACILITATED`,
   `OSS_UNION_SERVICES`,
   `IOSS_DISTANCE_SALE_LOW_VALUE`,
   `EXTERNAL_SCHEME_SERVICES`. The existing
   `SERVICES_DIGITAL_B2C_OSS` marker stays as a backwards-compatible
   alias for `OSS_UNION_SERVICES` and is deprecated through a code
   reference.
5. Add corresponding deterministic classifier rules. Each new rule
   follows the existing R-rule shape (predicate function + rule label
   + LIVA citation) and routes the criteria tuple to a
   regime-tagged `VATClassification`. The classifier must be
   exhaustive over the new transaction kinds; the rule list ordering
   stays deterministic.
6. Add a per-regime deductibility predicate
   `regime_allows_deduction(regime: OssIossRegime, scope) -> bool`
   anchored to the LIVA deduction articles (art. 163 vicies for
   Exterior, art. 163 tervicies for Unión, art. 163 octovicies for
   IOSS). All three articles share the same operative rule: the
   sujeto pasivo "no podrá deducir en la declaración-liquidación...
   cantidad alguna por las cuotas soportadas" inside the Modelo 369
   autoliquidation itself; recovery of input VAT happens through
   separate procedures (the regular IVA return for establecidos, the
   Eighth/Thirteenth Directive procedures for non-establecidos). The
   predicate therefore returns `False` for every regime when the
   scope is "within the Modelo 369 autoliquidation"; broader scopes
   route to the establecido / non-establecido distinction the LIVA
   articles encode. The predicate body and its tests are part of the
   substrate-extension slice; the corpus excerpts for the three
   deduction articles are pulled and committed alongside this ADR
   so the slice has the source-of-truth in the repository before
   implementation begins.
7. Extend per-destination rate windows in
   `registry/aeat/vat/rates.toml` rather than introducing a separate
   regime-scoped table. The existing 27-state coverage already
   provides destination-country VAT rates; the rate-window selector
   gains an optional `applicable_regimes` field that defaults to
   "any". The load-time non-overlap invariant expands to enforce
   non-overlap per `(member_state, kind, applicable_regimes)` tuple.
8. Introduce a new `DataBindingDefinition.source` value
   `ledger_oss_aggregation` for the registry. The binding selector
   declares the regime, the destination Member State, the
   `VATRateKind`, and the `InvoiceDirection` (issued / received). The
   runtime resolves the binding by aggregating ledger lines whose
   classification matches the selector across the period covered by
   the snapshot.
9. Model Modelo 369 as a single modelo with three revisions, one per
   Esquema. Each revision carries its own `period_selector`, cadence
   (`monthly` for Importación, `quarterly` for the others), filing
   schedule, deadline windows, and casillas / bindings tagged with
   the regime. This avoids polluting the modelo schema with a
   profile-conditional cadence selector and lets the existing
   single-cadence-per-revision invariant hold.
10. Sequence Modelo 369 as a multi-slice rollout under this ADR:
    - Substrate-extension slice (decisions 1-7).
    - `IvaRate` teardown slice migrating
      `aeat.domain.invoices._enums.IvaRate` to a registry-backed
      factory whose percentages come from `lookup_rate`.
    - Rental-imputación teardown slice migrating
      `IMPUTACION_RATE_RECENT_REVISION` and
      `IMPUTACION_RATE_OLD_OR_NO_REVISION` to
      `registry/aeat/legal/irpf.toml` parameters with LIRPF article
      85 citations and exposing them through the registry's
      parameter lookup.
    - Boundary-tightening slice constraining
      `aeat.application.review._edit.iva_rate` /
      `retention_rate` to the registry-backed enum and narrowing
      `aeat.domain.invoices._validators.validate_country_code` to
      the closed `EUMemberState | OtherCountry` taxonomy.
    - Ledger-binding slice introducing the
      `ledger_oss_aggregation` source kind and the runtime resolver.
    - Modelo 369 registry slices (one per Esquema revision) that
      consume the substrate plus the binding, with explicit live
      cross-reference guards, deadline windows, casillas, formulas,
      and per-Member-State export records.
11. Block Modelo 369 registry slices on the prior slices in the
    sequence. A foundation-only Modelo 369 commit that bypasses the
    teardown slices and pretends the substrate is already centralized
    would defeat this ADR's purpose; the registry validator must
    reject any Modelo 369 binding that references rate values not
    served by the substrate.
12. Catalogue HAC/610/2021 articles 1, 2, 3 and the LIVA OSS regime
    articles (163 septiesdecies, 163 octiesdecies, 163 unvicies, 163
    duovicies, 163 quinvicies, 163 sexvicies, 163 septvicies) as
    article-scoped corpus excerpts under `corpus/normatives/html/`
    before the substrate-extension slice lands. The full HAC/610/2021
    BOE order is also captured. No subsequent BOE amendments to
    HAC/610/2021 were found in the consolidated text as of this ADR's
    date.

## Proposed Substrate Shape

```text
class OssIossRegime(StrEnum):
    EXTERNAL_SCHEME = "external_scheme"
    UNION_SCHEME = "union_scheme"
    IMPORT_SCHEME = "import_scheme"

REGIME_PERIODICITY: Mapping[OssIossRegime, Cadence] = MappingProxyType({
    OssIossRegime.EXTERNAL_SCHEME: Cadence.QUARTERLY,
    OssIossRegime.UNION_SCHEME: Cadence.QUARTERLY,
    OssIossRegime.IMPORT_SCHEME: Cadence.MONTHLY,
})

class IossFilerRole(StrEnum):
    DIRECT = "direct"            # HAC/610/2021 art. 2(c)
    INTERMEDIARIO = "intermediario"  # HAC/610/2021 art. 2(d)

class TransactionKind(StrEnum):
    # ... existing members ...
    OSS_UNION_GOODS_DISTANCE_SALE = "oss_union_goods_distance_sale"
    OSS_UNION_GOODS_INTERFACE_FACILITATED = "oss_union_goods_interface_facilitated"
    OSS_UNION_SERVICES = "oss_union_services"
    IOSS_DISTANCE_SALE_LOW_VALUE = "ioss_distance_sale_low_value"
    EXTERNAL_SCHEME_SERVICES = "external_scheme_services"

def regime_allows_deduction(regime: OssIossRegime, scope: DeductionScope) -> bool:
    # LIVA art. 163 vicies / 163 tervicies / 163 octovicies
    ...
```

## Proposed Modelo 369 Revision Shape

```text
ModeloDefinition
  id = "369"
  cadence = "ad_hoc"          # parent placeholder; the active
                              # cadence lives on each revision
  revisions:
    "esquema-exterior":
      cadence = "quarterly"
      period_selector = { year_from = 2021,
                          periods = ["1T","2T","3T","4T"] }
      regime = OssIossRegime.EXTERNAL_SCHEME
      bindings = [...]        # ledger_oss_aggregation per
                              # destination Member State
      formulas = [...]        # per-line totals + autoliquidation total
      deadline_windows = [...]   # mes natural siguiente al final
                                 # del trimestre
    "esquema-union":
      cadence = "quarterly"
      regime = OssIossRegime.UNION_SCHEME
      ...
    "esquema-importacion":
      cadence = "monthly"
      period_selector = { year_from = 2021,
                          periods = ["01","02",...,"12"] }
      regime = OssIossRegime.IMPORT_SCHEME
      ...
```

The schema's existing `cadence` field on the modelo is set to
`ad_hoc` (the parent value) to express that the active cadence lives
on the revision; the registry validator gains a check that any modelo
declaring per-revision cadences must declare a parent cadence of
`ad_hoc`. Existing modelos keep their single-cadence pattern and the
check applies only to revisions that declare an explicit cadence
override.

## Proposed Ledger Binding Shape

```text
DataBindingDefinition
  id = "modelo-369-union-de-services-21pct"
  source = "ledger_oss_aggregation"
  selector = {
    regime = "union_scheme",
    destination_member_state = "de",
    rate_kind = "general",
    invoice_direction = "issued",
    transaction_kinds = ["oss_union_services"],
  }
  aggregation = { op = "sum", field = "iva_amount" }
  legal_refs = ["ley-37-1992:art-163-unvicies",
                "orden-hac-610-2021:art-1"]
  source_refs = ["aeat-dr-369"]
```

The runtime resolves the binding by:

- Loading ledger lines for the snapshot's filing period.
- Filtering to lines whose classification matches the selector. The
  classification axis comes from `aeat.domain.vat.classify_vat`,
  which itself is registry-backed (per the substrate decisions above).
- Aggregating the matched lines through the declared `aggregation` op.
- Returning the resolved value to the formula runtime as the binding
  value, identical in shape to existing binding sources.

The selector keys (`regime`, `destination_member_state`, `rate_kind`,
`invoice_direction`, `transaction_kinds`) are part of the registry
schema's binding selector contract; the registry validator rejects
ledger-aggregation bindings whose selector keys do not resolve
through the substrate.

## Teardown Plan

This ADR sequences the three teardowns identified by the rate-shadow
sweep:

- Teardown A: `aeat.domain.invoices._enums.IvaRate` migrates from a
  hardcoded percentage map to a registry-backed factory.
  `iva_rate_percentage(rate)` becomes a wrapper around
  `aeat.domain.vat.lookup_rate` keyed by the snapshot's filing year.
  Consumers in `aeat.domain.invoices._models`, the invoices test
  suite, and the review application call the new wrapper. The CLI
  invoice parser at `aeat.entrypoints.cli._invoice` keeps its inline
  string mapping but the resulting enum value goes through the
  registry-backed wrapper.
- Teardown B: `aeat.domain.rental._aggregates` constants
  (`IMPUTACION_RATE_RECENT_REVISION`,
  `IMPUTACION_RATE_OLD_OR_NO_REVISION`,
  `CATASTRAL_REVISION_LOOKBACK_YEARS`) move to
  `registry/aeat/legal/irpf.toml` as `ParameterDefinition` entries
  with LIRPF article 85 citations. Their consumers (the rental
  aggregator and Modelo 100 IRPF construct) call the registry's
  parameter lookup. The Python module retains a thin facade for type
  signatures but no numeric literals.
- Teardown C: `aeat.application.review._edit.iva_rate` and
  `retention_rate` switch from `Decimal | None` to the
  registry-backed `IvaRate` (or `Optional[IvaRate]` /
  `Optional[RetentionRate]`). The country validator at
  `aeat.domain.invoices._validators.validate_country_code` narrows to
  `EUMemberState | OtherCountry` and rejects unknown codes at
  the schema boundary.

Each teardown lands as its own commit and carries its own
focused-test verification; no Modelo 369 registry slice merges before
Teardowns A, B, and C are reviewed.

## Corpus Prerequisites

The substrate-extension slice depends on the following corpus
artefacts already being committed under `corpus/normatives/html/`
before its tests run:

- `orden-hac-610-2021.html` — full BOE order.
- `orden-hac-610-2021-art-1.html` — Article 1 (Aprobación).
- `orden-hac-610-2021-art-2.html` — Article 2 (Obligados / período).
- `orden-hac-610-2021-art-3.html` — Article 3 (Plazo).
- `ley-37-1992-art-163-septiesdecies.html` — LIVA common
  definitions for all three OSS regimes (Estado miembro de consumo,
  Estado miembro de identificación, declaraciones-liquidaciones
  periódicas).
- `ley-37-1992-art-163-octiesdecies.html` — LIVA OSS Exterior
  (Ámbito).
- `ley-37-1992-art-163-unvicies.html` — LIVA OSS Unión (Ámbito).
- `ley-37-1992-art-163-duovicies.html` — LIVA OSS Unión (Obligaciones
  formales).
- `ley-37-1992-art-163-quinvicies.html` — LIVA IOSS (Ámbito).
- `ley-37-1992-art-163-sexvicies.html` — LIVA IOSS (Devengo).
- `ley-37-1992-art-163-septvicies.html` — LIVA IOSS (Obligaciones
  formales).

These excerpts are pulled and committed in the corpus slice that
accompanies this ADR. No subsequent BOE amendment to HAC/610/2021
was found in the consolidated text; the corpus is therefore complete
as of this ADR's date.

The deduction articles (LIVA art. 163 vicies for Exterior, LIVA
art. 163 tervicies for Unión, LIVA art. 163 octovicies for IOSS) are
also pulled and committed alongside this ADR so Decision 6's
deductibility predicate can be derived directly from BOE text during
the substrate-extension slice:

- `ley-37-1992-art-163-vicies.html` — LIVA OSS Exterior (Derecho a
  la deducción).
- `ley-37-1992-art-163-tervicies.html` — LIVA OSS Unión (Derecho a
  la deducción).
- `ley-37-1992-art-163-octovicies.html` — LIVA IOSS (Derecho a la
  deducción).

All three articles share the same operative rule that grounds
Decision 6: deduction is forbidden inside the Modelo 369
autoliquidation, with recovery routed through the regular IVA
return for establecidos and the Eighth/Thirteenth Directive
procedures for non-establecidos.

## Constraints

- The substrate stays Pydantic-strict and frozen. The new
  enumerations are closed `StrEnum` types; the new classifier rules
  follow the existing R-rule shape (predicate + label + LIVA
  citation) and remain deterministic.
- The registry validator stays the only filing-grade gate. The
  ledger-aggregation source must validate selector keys, regime ↔
  cadence consistency, destination Member State membership in
  `EUMemberState`, and rate-kind membership in `VATRateKind` at
  load time.
- No Modelo 369 binding may reference a rate value that is not
  served by `registry/aeat/vat/rates.toml`. The validator must
  enforce this; any drift fails snapshot creation.
- The teardown slices may not silently rename or hide existing
  consumers. Each teardown carries a `support_removal_decision`
  entry where the old surface was filing-grade (per the parent
  ADR's no-relaxed-runtime-modes rule).
- This ADR does not authorize any AEAT remote-state mutation. The
  Modelo 369 registry slices, when they land, must declare
  `static_official_documentation` and `authenticated_read_surface`
  cross-references with the same forbidden-actions list used by the
  prior modelo foundations.

## Considerations

The audit's first loop established that the substrate is mature and
that the OSS work is taxonomy + classifier extension rather than a
greenfield build. The second-loop sweep showed that the codebase
still carries hardcoded filing-grade rate values that would
contaminate any Modelo 369 binding the moment it landed. Sequencing
the teardown slices ahead of the registry slices is the only
defensible order: a foundation-only Modelo 369 commit would either
have to reference the existing shadows (defeating the substrate) or
declare a non-functional binding (defeating the registry's
load-time validator).

The decision to keep a single Modelo 369 with three revisions —
rather than three separate modelos — preserves the modelo identity
that AEAT publishes (one form 369, three regime sections) while
isolating the cadence variation to the revision boundary. The
existing schema's single-cadence-per-revision invariant holds; only
the parent modelo's cadence becomes `ad_hoc` to express the
per-revision override, and the validator gains a small check to
reject mixed configurations.

The ledger-binding shape introduces a new `source` value
(`ledger_oss_aggregation`) rather than overloading existing values.
This keeps the binding contract explicit, lets the validator reject
selector keys that don't apply to ledger sources, and gives the
runtime a single resolver entry point for VAT-driven aggregations.
The same shape will be reusable when Modelos 303 and 390 land their
registry slices.

## Constraints on Future Loops

Per the user directive that Modelo 369 design is conditional on
looping audits, discovery, and research, this ADR does not foreclose
further loops. If a subsequent audit surfaces additional shadow
surfaces, additional regime-specific rules, or additional
ledger-aggregation requirements that this ADR does not cover, a
follow-up ADR or ADR amendment must land before the affected slice.
The ADR's pre-implementation gates (corpus prerequisites,
substrate-extension test pass, teardown verification) prevent
silent drift between this proposal and the eventual implementation.

## Implementation

The implementation lands as the multi-slice rollout sequenced in
Decision 10. Each slice is its own commit and carries its own
focused-test pass plus the heterogeneous-bundle disclosure if other
agents' files leak into the staging area at commit time. The
registry validator gains the new gates described in the Constraints
section as part of the substrate-extension slice and the
ledger-binding slice; subsequent slices rely on those gates to fail
hard when drift occurs.

## Rationale

The substrate-in-place extension is the lowest-risk path because it
preserves the existing 27-state rate table, the deterministic
classifier, and every other invariant the calculation-truth-registry
parent ADR relies on. A sibling `aeat.domain.oss/` module would
duplicate the Member State enumeration, the rate-window scaffolding,
and the classifier shell, which the parent ADR explicitly bans.

The ledger-aggregation binding source is the smallest surface that
satisfies Modelo 369's needs while remaining reusable for Modelos
303 and 390. The alternative — letting Modelo 369 declare
casilla-level formulas that hand-roll ledger filters — would push
filing-grade aggregation logic into the formula runtime and defeat
the registry's claim that data lives in TOML.

The single-modelo-three-revisions shape mirrors the AEAT publication
of Modelo 369 as one form with three regime sections. Splitting it
into three modelos would invent registry identity that AEAT does
not publish and would break the cross-modelo dependency declarations
that future work depends on.

## Consequences

- The substrate-extension slice will touch the `aeat.domain.vat`
  module surface (new enumerations, new classifier rules, expanded
  rate-window selector). The Pydantic-strict invariants and the
  test suite already cover the shape; the additions extend the
  fixture set.
- The teardown slices will touch invoice, rental, review, and CLI
  surfaces. Each teardown should be reviewed independently; the
  rental-imputación teardown in particular touches Modelo 100
  consumers and may interact with concurrent Modelo 100 work.
- The ledger-binding slice will introduce the
  `ledger_oss_aggregation` source kind and the runtime resolver. The
  resolver's filtering predicate must be deterministic and
  side-effect-free; the registry validator gains a check that the
  resolver is registered before any binding of that kind can resolve.
- The Modelo 369 registry slices will land per Esquema and consume
  the substrate plus the binding. The first slice (Esquema Unión —
  the most common autónomo case for OSS) sets the precedent; the
  Importación and Exterior revisions follow.
- Once this ADR clears review, the calculation-truth-registry parent
  plan must gain a new wave entry for the substrate-extension and
  teardown work, plus an updated Wave 13 (Modelo 369) ledger that
  blocks the registry slices on the substrate work.
