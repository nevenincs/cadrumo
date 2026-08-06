---
tags:
  - '#adr'
  - '#convenio-doble-imposicion'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:27d3de436ab125c9ba302823a258c539cc7a2d5957ac20138b079ea97c8bb9e3'
related:
  - "[[2026-06-30-convenio-doble-imposicion-research]]"
  - "[[2026-05-27-m210-irnr-full-engine-adr]]"
  - "[[2026-05-27-non-resident-irnr-axis-adr]]"
  - "[[2026-06-30-m210-categorical-conditional-predicate-adr]]"
---

# `convenio-doble-imposicion` adr: `Convenio doble imposicion treaty-rate override framework` | (**status:** `accepted`)

## Problem Statement

Issue #537 (P1, parent of a treaty tranche; child #558 Spain-Argentina) asks for a framework
to apply bilateral double-taxation treaty (CDI) overrides to Spanish non-resident income tax.
Research finds the override is **not absent but narrow**: a working `(country, tipo_renta)`
rate-replacement mechanism already ships on the M210 calculate path (`m210_resolve_rate` op,
`m210-convenio-rates` parameter, `ConvenioRateRow` schema, three seed treaties), governed by
`2026-05-27-m210-irnr-full-engine-adr` D2.4. Four structural gaps make that mechanism unfit to
be the "framework" #537 needs:

1. It is `m210_*`-named and physically located under `modelos/210/`, so the day a second IRNR
   consumer lands (M216 retenciones a no residentes -- dividends/interest/royalties), the
   treaty data must either be duplicated per-modelo or reached across a modelo boundary.
2. The income-type axis `tipo_renta` is an untyped free-text casilla, violating the
   closed-value-set mandate and already forcing a peer campaign to work around it.
3. A second, divergent treaty surface -- the `_CONVENIO_BY_COUNTRY` Python literal feeding
   `TaxpayerProfile.convenio_aplicable` -- covers a different country set than the rate table
   and is an inlined regulatory literal.
4. The rate row cannot distinguish a flat treaty rate from a *ceiling* ("may not exceed X%"),
   an *allocation*, or an *exemption*, so "mas favorable" / limitation-of-benefits is honoured
   only by numeric coincidence today.

This ADR decides how to generalise, type, reconcile, and bound that surface into a reusable,
single-authority treaty-override framework. Calc/advisory only; no live filing
(`aeat-safety-legal-gates`).

## Considerations

- **One consumer today, more projected.** Only M210 exists. The framework's value is realised
  on the second consumer, so the design must remove the `m210_*` coupling without inventing
  speculative machinery (PE thresholds, withholding modelos) that no current modelo exercises.
- **Canonical-mechanism discipline.** `calculation-source-canonical-mechanism` and
  `one-aggregation-path-pull-equals-calculate` forbid a parallel rate path. The treaty override
  is one branch of the single tipo-de-gravamen resolution, not a second resolver.
- **No-legacy freedom.** `no-legacy-compatibility` permits deleting the `m210_*` names and the
  M210-local parameter outright (unreleased pre-beta, sole consumer) -- no shim, no bridge.
- **Registry authority flow.** A treaty authoring surface must ride the TOML -> loader/compiler
  -> strict schema -> authority -> snapshot pipeline, with the new tree included in the
  cache-invalidation fingerprint.
- **Filing-grade legal grounding.** Every treaty rate is regulated. It must cite the binding
  treaty article, ground that article in the bundled consolidated CDI corpus, cross-check the
  figure against live BOE/AEAT, and carry an honest `reviewed_by` pending operator re-stamp.
- **Peer WIP.** `domain/deadlines/_models.py` (home of `_CONVENIO_BY_COUNTRY`) is under active
  uncommitted edit by the today-dated `m210-categorical-conditional-predicate` campaign; the
  D3 reconciliation must use the apply-cached gated discipline.

## Considered options

The decision is presented as four sub-decisions (D1-D4); each names the alternatives at the
same level of abstraction.

### D1 -- Where treaty data lives

- **Option 1A: keep treaty rates per-modelo, standardise the schema.** Each consuming modelo
  carries its own `convenio_rate_table` parameter. *Pro:* zero new loader surface; matches the
  current shape. *Con:* a treaty is then authored once per modelo, duplicating BOE-grounded
  rows and inviting per-modelo drift -- the exact failure F3 already exhibits between two
  surfaces. Rejected.
- **Option 1B: generalise the table but leave it under `modelos/210/`.** Rename to a generic
  parameter, keep the file under M210. *Pro:* smallest move. *Con:* a cross-cutting authority
  physically owned by one modelo; the second consumer reaches across a modelo boundary to read
  it. Rejected as a hidden coupling.
- **Option 1C (chosen): a dedicated cross-cutting treaty authoring tree.** Author one file per
  treaty under a new `registry/aeat/treaties/` surface (sibling to the existing cross-cutting
  `legal/` tree), keyed by counterpart country, carrying per-income-type override rows and
  room for future PE thresholds. The loader compiles it into a `ConvenioAuthority` snapshot
  projection any modelo rate formula consumes. *Pro:* treaty authored once, single authority,
  ready for M216; mirrors how `legal/` is already a non-modelo-scoped registry surface. *Con:*
  a new loader path and fingerprint entry. Accepted -- the con is one-time and mandated by
  registry-authority-flow anyway.

### D2 -- The override mechanism and precedence

- **Option 2A: flat replacement only (status quo).** Treaty row carries one Decimal that
  replaces the domestic rate. *Pro:* simplest. *Con:* cannot express a treaty *ceiling*,
  *exemption*, or honestly compute "mas favorable"; correct today only because 10% < 19% by
  luck. Rejected.
- **Option 2B: per-formula conditional.** Already rejected by the parent ADR (blows up the
  formula DSL, enumerates ~90 treaties in formula bodies). Rejected, restated for completeness.
- **Option 2C (chosen): typed override kind, single resolution path.** Add a closed core enum
  `ConvenioOverrideKind` {`flat`, `ceiling`, `allocation_domestic_tariff`, `exempt`}. The one
  generalised tipo-de-gravamen op resolves domestic and treaty in the same pass (no parallel
  path): on a matched row it applies the kind -- `flat` replaces, `ceiling` applies
  `min(domestic, treaty)`, `allocation_domestic_tariff` delegates the amount to the domestic
  tariff (today's `DOMESTIC_TARIFF` sentinel, now typed), `exempt` yields 0. Missing-row stays
  BLOCKING (`no-silent-under-declaration`). Treaty eligibility (residence certificate,
  limitation-of-benefits) is surfaced as a non-blocking advisory `Notice`, never silently
  trusted. Accepted.

### D3 -- The profile / income-tagging axis

- **Option 3A: keep free-text `tipo_renta` and the dual treaty surfaces.** *Con:* perpetuates
  the untyped axis (F2) and the drift (F3). Rejected.
- **Option 3B (chosen): type the income axis, single residence fact, single treaty authority.**
  Residence selection stays on the existing `country_of_fiscal_residence` (no new field).
  Replace the free-text `tipo_renta` value with a new closed core `StrEnum TipoRentaIrnr`
  (`general`, `ue_residente`, `pension`, `interest`, `ganancia_patrimonial`, `inmobiliaria`),
  surfaced as a CLI `Choice`. Retire the `_CONVENIO_BY_COUNTRY` Python literal: derive
  `convenio_aplicable` from the `ConvenioAuthority` so the informational and calc surfaces read
  one authority. Retire the redundant `convenio_doble_imposicion_country` profile field in
  favour of `country_of_fiscal_residence`. Accepted.

### D4 -- Scope and rollout

- **Option 4A: full treaty network now (~90 CDIs).** Rejected -- starves every other campaign,
  and each treaty needs grounded, operator-reviewable rates.
- **Option 4B (chosen): bounded first slice + enrolment contract.** Ship the framework (treaty
  tree, loader, `ConvenioAuthority`, `ConvenioOverrideKind`, `TipoRentaIrnr`, generalised op),
  migrate the three existing treaties into it with no rate change, deepen Argentina (#558) with
  any additional income-type rows the bundled corpus grounds, and add ONE further high-traffic
  CDI already named by the informational map (Germany BOE-A-2012-3669 proposed as the cleanest
  corpus candidate; final pick deferred to grounding). PE thresholds and the M216 withholding
  consumer are explicitly out of slice; the treaty schema leaves room for them. Children such as
  #558 enrol by authoring a treaty file -- no framework change. Accepted.

## Constraints

- **Depends on the M210 engine ADRs.** This decision generalises machinery accepted by
  `2026-05-27-m210-irnr-full-engine-adr` (the convenio dispatch) and
  `2026-05-27-non-resident-irnr-axis-adr` (the residence profile axis). Both are accepted and
  stable; this ADR supersedes only the *location and naming* of the D2.4 convenio surface, not
  its safety contract.
- **Typed-axis migration touches a peer-edited file.** Retiring `_CONVENIO_BY_COUNTRY` and the
  `convenio_doble_imposicion_country` field edits `domain/deadlines/_models.py`, which carries
  live uncommitted peer WIP. The plan must re-read HEAD and use the apply-cached gated drive;
  it is not a blocker but a sequencing constraint.
- **No external library or frontier risk.** The work is registry TOML, pydantic v2 schema, a
  StrEnum, and a formula-runtime op -- all established patterns. No new dependency.
- **Legal grounding is the gating constraint, not code.** The first slice is rate-limited by
  how many treaty articles can be grounded against the bundled corpus and cross-checked against
  live BOE/AEAT, not by engineering effort. Ungrounded rates do not ship.
- **Registry parity gates.** The new `ConvenioOverrideKind` enum and `TipoRentaIrnr` enum must
  satisfy the core-enum / registry-parity discipline; the treaty tree must enter the registry
  cache fingerprint so a TOML edit invalidates the snapshot.

## Implementation

A high-level shape, not a plan.

**Authoring surface (D1).** A new `registry/aeat/treaties/` tree, one file per treaty
(`es-ar.toml`, `es-gb.toml`, ...). Each declares the counterpart country, the treaty BOE
`document_id`, and a list of override rows keyed by `TipoRentaIrnr`, each row carrying the
override kind, the rate (where applicable), and `legal_refs`/`legal_ref_anchor` into the
treaty article in `legal/`. The loader compiles the tree into a `ConvenioAuthority` exposing
`resolve(country, tipo_renta, year) -> ConvenioOverride | None`, projected onto the snapshot
the same way `legal/` entries are. The M210-local `m210-convenio-rates` parameter is deleted.

**Resolution (D2).** The current `m210_resolve_rate` op is generalised (renamed to a
modelo-neutral `irnr_resolve_tipo_gravamen` and moved off the `m210_*` namespace) to consult
the `ConvenioAuthority` projection instead of an M210-local parameter. On a matched override it
branches on `ConvenioOverrideKind`: flat replace, `min(domestic, treaty)` ceiling, domestic
tariff delegation, or zero. The missing-row BLOCKING sentinel and the verification-sweep
rewrite are preserved verbatim. Treaty-eligibility advisories ride the typed `Notice` channel.

**Typed axes (D3).** `TipoRentaIrnr` and `ConvenioOverrideKind` are declared in `core/`. The
`tipo_renta` casilla loader hydrates the enum at the boundary; the CLI argument declares the
enum so click renders the accepted set. `_CONVENIO_BY_COUNTRY` is deleted and
`convenio_aplicable` reads the authority; the `convenio_doble_imposicion_country` field is
removed and its sole selection role folded onto `country_of_fiscal_residence`.

**Slice (D4).** Migrate `es-gb` / `es-ma` / `es-ar` unchanged, deepen `es-ar`, add one further
grounded CDI, and pin a continuity test mirroring `test_modelo_210_irnr_continuity.py` so the
generalised path yields the same cuota the M210-local path produced for the seeded personas
(anti-regression, not a tautology -- the expected rates trace to treaty-article corpus text).

## Rationale

The chosen options share one through-line: there is already a correct, grounded, safety-gated
treaty mechanism, so the right move is to *lift* it to a single cross-cutting authority and
*type* its two untyped axes, not to rebuild it. Option 1C mirrors the existing `legal/` tree,
the project's established pattern for non-modelo-scoped registry authority, so the second
consumer (M216) reads treaty data without a modelo-boundary reach (research F1). Option 2C
turns the "ceiling vs flat" coincidence (research F5) into computed data, making "mas
favorable" honest while keeping the single resolution path the canonical-mechanism rule
demands. Option 3B closes the closed-value-set violation (research F2) and the dual-surface
drift (research F3) in one move, both already costing adjacent work. Option 4B respects the
open-ended-campaign cadence and the legal-grounding rate limit: the framework lands once, and
each treaty -- including the #558 child -- enrols as grounded data behind an operator re-stamp.

## Consequences

- **Gain:** one treaty authority, grounded once per treaty, ready for the withholding modelos;
  the income axis and override kind become typed, gate-checkable data; the two divergent
  country surfaces collapse to one.
- **Gain:** "mas favorable", ceiling, and exemption treaties become expressible, removing a
  latent wrong-rate risk that today survives only because the seeded numbers happen to coincide.
- **Cost (accepted):** a new loader path, two new core enums, and a behaviour-preserving rename
  of the M210 op and deletion of its local parameter -- a one-time atomic relocation that must
  land with its consumers and tests in a single commit.
- **Cost (accepted):** the `_models.py` edits contend with live peer WIP and must be sequenced
  with the apply-cached drive.
- **Bounded:** PE thresholds, employment-income articles, and the M216 withholding consumer are
  deferred; the framework leaves room but does not model them, so #537 is advanced, not closed,
  by the first slice.
- **Honesty posture:** every shipped treaty rate is agent-prepared, grounded against the bundled
  consolidated CDI corpus, cross-checked against live BOE/AEAT, and stamped with honest
  `reviewed_by` provenance pending operator re-stamp before any filing-grade reliance.
