---
tags:
  - '#adr'
  - '#cross-period-prorrata'
date: '2026-07-05'
modified: '2026-07-08'
related:
  - "[[2026-07-01-iva-complexity-hardening-scope-adr]]"
  - "[[2026-07-01-iva-complexity-hardening-scope-research]]"
  - "[[2026-06-19-silent-zero-base-aggregation-adr]]"
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
  - "[[2026-07-05-silent-zero-base-aggregation-audit]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]"
  - "[[2026-07-01-iva-bienes-inversion-regularizacion-adr]]"
  - '[[2026-07-06-cross-period-prorrata-research]]'
---
# `cross-period-prorrata` adr: `Cross-period prorrata model: provisional carry, in-year apportionment, settlement regularisation` | (**status:** `accepted`)

## Problem Statement

The silent-zero-base campaign closed its bounded mirrors but formally deferred its
two prorrata volume rows (`W01.P02.S03`/`S04`) to "an undecided cross-period
prorrata model": the regulated IVA prorrata is not a per-period computation, so no
per-quarter binding can ship it honestly. The sibling scope ADR
(`2026-07-01-iva-complexity-hardening-scope-adr`, proposed) named the shape —
provisional carry plus settlement regularisation, advisory-first — but left the
concrete cross-period model undecided: where the provisional and definitive
percentages live, how the prior-year definitive is carried under the existing
carry disciplines, whether and how in-year (1T-3T) deducible cuotas are
apportioned at all, and what exactly un-silences the mixed trader's deduction.

The regulated flow, verified verbatim against the bundled consolidated LIVA
(`ley-37-1992.html`, arts. 102-106): prorrata applies when the taxpayer performs
both operations with and without the right to deduct (art. 102.Uno); under
prorrata general only the deduction percentage of soportado is deductible **in
each liquidation period** (art. 104.Uno); the percentage provisionally applicable
each year is **the prior year's definitive** (art. 105.Uno), with two regulated
alternatives — an AEAT-approved distinct provisional (art. 105.Dos) and the
inicio-de-actividades proposed percentage (art. 105.Tres via art. 111.Dos); **in
the last declaración-liquidación of the year** the taxpayer computes the
definitive prorrata from the year's actual operations and regularises the
provisional deductions (art. 105.Cuatro), the percentage applying to the year's
total deductible soportadas (art. 105.Seis). This provisional→definitive flow is
inherently cross-period and cross-year.

At HEAD the compute half exists and is stable: the domain substrate
(`domain/iva/_prorrata.py`) implements art-102/104 general computation with
ROUND_CEILING, `compute_prorrata_definitiva_anual`,
`compute_regularizacion_prorrata_anual` (art. 105.Cuatro delta, correctly
gate-free), the art-106 especial classification, and the sectoral predicate. The
M303 registry computes `iva.prorrata-porcentaje` from operator-entered annual
volume casillas with a full-deduction default when no volumes are declared;
casilla 44 is `input_kind = manual`. A settlement-period advisory
(`_prorrata_regularizacion_advisory.py`) reads the prior-year definitive from the
local observation catalogue and alerts; `BindingSourceKind.PRORRATA_REGULARIZACION`
sits in `DEFERRED_SOURCE_KIND_TARGETS` awaiting "the provisional-carry store".
What does NOT exist: any carry store, any in-year apportionment of deducible
cuotas (a mixed trader's ledger aggregation deducts 100% during 1T-3T today), and
any annual volume rollup. A semantic-search hit for
`application/aggregation/_prorrata.py` orchestrators proved to be a stale index
entry — no such module exists at HEAD.

This ADR decides the cross-period model so the deferral has a buildable design.

## Considerations

- The prior-year definitive percentage is, in the normal case, derivable from the
  prior settlement filing: `iva.prorrata-porcentaje` is a computed casilla whose
  observation the filing path already persists (`persist_filed_revision_observation`),
  revision-stamped per the `carried-observations-stamp-their-revision` rule. The
  advisory already exploits this same-modelo prior-filing lookup.
- The art. 105.Dos AEAT-authorised provisional and the art. 105.Tres
  inicio-de-actividades percentage are NOT derivable from any prior filing — they
  are per-taxpayer facts with an external authorisation. A pure
  observation-carry model cannot represent them; a pure operator-typed model
  loses the filed-history cross-check for the normal case.
- Art. 104.Uno makes the provisional percentage bite in EVERY liquidation
  period, not only at settlement: a mixed trader deducting 100% in 1T-3T
  over-deducts every quarter. The current model is silently wrong in-year for
  mixed traders, independent of casilla 44.
- The definitive percentage needs full-year con-derecho/sin-derecho volumes with
  the art. 104.Tres exclusions (permanent establishments abroad, bienes de
  inversión disposals, non-habitual financial/inmobiliario operations, art-7
  non-sujetas, art. 9.1.d autoconsumos). The ledger can project most turnover
  but cannot classify every exclusion (subvenciones, capital-goods disposals
  live in the bienes-inversión register; habituality is a judgment fact), so a
  ledger-only definitive volume would be a wrong regulated number for some
  traders — the same defect class the silent-zero ADR rejected per-period sums
  for.
- Binding rules: `revision-resolution-is-law-determined` (prior settlement
  revision resolved via `select_revision`, stored ids only asserted),
  `carried-observations-stamp-their-revision` (cross-year reads re-confirm the
  stamp; divergence blocks, missing stamp advises),
  `period-filter-single-boundary-authority` (the annual window is
  `Period.contains` over the ejercicio's periods, no ad-hoc date math),
  `one-aggregation-path-pull-equals-calculate` (one shared resolver set),
  `no-silent-under-declaration` and `no-dormant-source-resolvers` (a deferred
  source advises; promotion co-lands with enrollment),
  `sensitive-financial-data-secure-storage-only` (per-taxpayer facts persist
  only in the encrypted bucket-scoped substrate),
  `binding-values-carry-provenance` (the applied percentage rides on value
  provenance), `aeat-spanish-stem-naming` (prorrata/regularización stems).
- In-tree cross-period precedents: the IVA compensation wallet
  (profile-scoped period-state store + `iva_compensation_annual_partition`
  registry source) and the bienes-inversión register
  (`adapters/persistence/profile/bienes_inversion.py`: PROFILE_* secure-object
  namespace, singleton envelope, roundtrip + anti-tautology tested). The
  bienes-inversión automatic casilla-43 feed is BLOCKED on this feature's
  definitive-percentage source.

## Considered options

**O1 — Carry home: observation-only carry (previous_filing-style cross-year
binding on the prior settlement's `iva.prorrata-porcentaje`).** Pro: reuses the
stamped-observation discipline wholesale; zero new stores. Con: cannot represent
art. 105.Dos/Tres percentages, which are regulated first-class inputs; a
first-year or externally-filed taxpayer has no local prior observation and the
model dead-ends. REJECTED as sole home.

**O2 — Carry home: operator-typed profile fact only (a bare percentage field on
the taxpayer profile).** Pro: trivially covers 105.Dos/Tres. Con: loses the
filed-history cross-check for the normal 105.Uno case; a typo ships a wrong
regulated percentage with no contradiction surface; no per-ejercicio history.
REJECTED.

**O3 — Carry home: per-ejercicio prorrata register seeded from the prior
settlement observation, with provenance-tagged overrides (CHOSEN).** A
profile-scoped encrypted register holds one entry per ejercicio (regime,
provisional percentage + provenance, definitive percentage + volume inputs once
settled). The 105.Uno normal case is SEEDED from the stamped prior observation
and cross-checked against it forever after; 105.Dos/Tres values are recorded
with their provenance and authorisation reference. One home represents all three
regulated provenances and keeps history.

**O4 — In-year apportionment: leave 1T-3T at full deduction, regularise
everything at 4T.** Pro: smallest change. Con: art. 104.Uno applies the
percentage in each liquidation period; full in-year deduction is a wrong
regulated number every quarter for mixed traders and overstates casilla-45/71
in-year. REJECTED.

**O5 — In-year apportionment: apply the register's provisional percentage inside
the one shared ledger IVA deducible aggregation (CHOSEN),** parameterised from
the register, provenance-carried, with non-prorrata taxpayers byte-identical.

**O6 — Definitive volumes: ledger-only annual rollup.** Con: cannot classify
every art. 104.Tres exclusion; wrong regulated percentage for some traders.
REJECTED as the authority (kept as a reconciliation check).

**O7 — Definitive volumes: operator-declared annual volume casillas as the
authority, ledger annual rollup as a divergence advisory (CHOSEN).** The declared
volumes are what the form files; the rollup surfaces contradiction instead of
silently substituting.

**O8 — Especial in the first model.** Con: needs per-input exclusive-use
classification across the ledger, a new surface; the +10% mandatory-especial
comparison (art. 103.Dos.2) needs the especial computation to exist first.
DEFERRED with the schema shaped to admit it.

## Constraints

- Parent stability: the general/especial/sectoral compute substrate
  (`2026-05-12` ADR, accepted) is stable and is consumed, not re-opened. The
  scope ADR (`2026-07-01-iva-complexity-hardening-scope-adr`, proposed) is
  refined, not contradicted: its Decisions 1/2/3 (annual rollup for the
  definitive math, profile-scoped carry, deferred-with-advisory first slice)
  are all preserved; this ADR concretises the carry-store shape, adds the
  in-year apportionment the scope ADR did not cover, and assigns volume
  authority to the declared casillas with the rollup as reconciliation.
- No fabricated regulated values: percentages come only from the stamped prior
  observation, an operator-recorded authorised/proposed value with provenance,
  or the substrate over declared annual volumes. There is no default provisional
  percentage. The full-deduction default remains strictly the
  no-prorrata case (no sin-derecho operations; LIVA art. 94).
- Registry authority: the especial +10% gate constant, the art. 104.Tres
  exclusion taxonomy, and rounding stay registry/corpus-grounded
  (`registry-calculation-legal-grounding`,
  `legal-grounding-verifies-bundled-authoritative-corpus`); the register holds
  taxpayer facts only.
- Secure storage: the register persists exclusively through the encrypted
  bucket-scoped secure-object substrate with save/load/equality roundtrip plus
  anti-tautology proof (`aeat-roundtrip-discipline`).
- Carry discipline: the seed read resolves the prior settlement revision via
  `select_revision` and re-confirms the observation's `stamped_revision_id`;
  divergence blocks the seed, a missing legacy stamp surfaces a non-blocking
  advisory. Local `app_filing` observations may feed the calculate-path carry
  but never substitute for official evidence
  (`local-filed-observations-are-non-official-evidence`).
- One aggregation path: the provisional apportionment and the settlement
  regularisation resolve through the shared resolver set consumed by both the
  calculate path and the Sheets-pull path, with a parity regression.
- Verification: the regularisation cuota and the apportioned deduction are
  proven against an AEAT Manual práctico IVA worked example or equivalent
  bundled oracle, never hand-computed from the same formulas
  (`no-tautological-calculation-tests`,
  `verification-grounding-needs-oracle-evidence`).

## Implementation

**Register (the carry home).** A per-ejercicio `ProrrataRegister` on the
bienes-inversión register pattern: a PROFILE_* secure-object namespace singleton
holding, per ejercicio and (future) sector: the regime
(`general | especial | none`), the provisional percentage in force with a closed
provenance enum (`carried_prior_definitiva | aeat_autorizada | inicio_actividad`)
and, for the non-carried provenances, the authorisation/proposal reference; and,
once settled, the definitive percentage with the volume inputs it derived from.
Typed pydantic models, strict, Spanish stems.

**Seeding (the cross-year carry).** At first use in an ejercicio, the
`carried_prior_definitiva` entry is seeded from the prior year's settlement-period
`iva.prorrata-porcentaje` observation: the prior revision is resolved by
`select_revision` for (M303, year−1, settlement period), the observation's
`stamped_revision_id` is re-confirmed, and the seeded entry records the source
observation identity. Whenever both a register entry and a prior observation
exist, they are cross-checked: contradiction between a `carried_prior_definitiva`
entry and the observation is a BLOCKING divergence finding; an `aeat_autorizada`
or `inicio_actividad` entry differing from the prior definitive is the regulated
case (art. 105.Dos/Tres) and surfaces an informational notice naming the
provenance, never silence. Precedence is a single declared ladder:
authorised/inicio provenance > carried prior definitive > no value (see
applicability below). No percentage is ever assumed.

**In-year apportionment (1T-3T and every non-settlement period).** When the
register holds an active `general` entry for the ejercicio, the shared ledger
IVA deducible aggregation applies the provisional percentage to the deducible
cuotas it resolves (art. 104.Uno + 105.Uno) inside the one aggregation path;
the applied percentage and its provenance ride on the binding value provenance
and the casilla observation trail. Bases stay unapportioned (the form declares
full bases; the percentage reduces cuotas). Non-prorrata taxpayers are
byte-identical to today.

**Settlement (4T/0A).** The definitive percentage is
`compute_prorrata_definitiva_anual` over the operator-declared annual volume
casillas (the existing registry mechanism, unchanged authority); an annual
ledger rollup of con-derecho/sin-derecho turnover — windowed by
`Period.contains` over the ejercicio's periods, art. 104.Tres exclusions applied
where classifiable — is computed alongside and raises a non-blocking divergence
advisory when it contradicts the declared volumes. Casilla 44 is fed by
`compute_regularizacion_prorrata_anual(annual deductible soportadas at
provisional, provisional %, definitive %)`; the same projection feeds the M390
annual regularisation field. On settlement the definitive percentage and its
volume inputs are written back to the register — that write is what seeds
year+1. The write-back co-travels with revision persistence (the
participation-index co-write pattern) so the register is rebuildable from the
observation catalogue.

**Source-kind promotion.** `PRORRATA_REGULARIZACION` stays DEFERRED (advisory
live, as today) until the register, seeding, apportionment, and settlement
projection are proven end to end against a bundled AEAT worked example; the
promotion then enrolls the resolver and flips the disposition registry in one
change (`no-dormant-source-resolvers`), following the
`iva_compensation_annual_partition` precedent already named in
`DEFERRED_SOURCE_KIND_TARGETS`. The bienes-inversión casilla-43 feed
(`BIENES_INVERSION_REGULARIZACION`, `promotion_depends_on`) consumes the same
definitive-percentage source and unblocks after.

**Applicability + non-silence (the silent-zero-base resolution).** Prorrata
applicability is derived, fail-closed-to-visible: prorrata applies when the
register holds an active entry OR the ejercicio shows sin-derecho volumes
(declared or ledger-projected). When prorrata applies and no provisional
percentage resolves through the ladder, every calculate in the ejercicio emits
an advisory naming the missing carry (first ejercicio: record the
inicio-actividad percentage; otherwise: seed or record the prior definitive),
and the settlement-period verify gate emits at least an ADVISORY finding —
never `verified_complete` with zero findings — mirroring the Modelo 200
`implies_nonzero` worked example of `no-silent-under-declaration`. A mixed
trader can no longer silently deduct 100% in-year, silently skip casilla 44, or
silently zero the deducible side; the fully-taxable trader keeps the art-94
full-deduction default untouched.

**Deferred, honestly.** Prorrata especial per-input apportionment and the
art. 103.Dos.2 +10% mandatory-especial comparison advisory (needs especial to
exist); sectores diferenciados (art. 9.1.c / 101) per-sector registers beyond
the schema slot; the art. 104.Tres financial/inmobiliario denominator
special-computation rules beyond the exclusion set; art. 105.Cinco interrupted
activity three-year rule; automatic art-104.Tres exclusion classification in
the ledger rollup (the rollup stays a reconciliation check until then). The
register schema carries regime and sector axes from birth so these land without
migration (`no-legacy-compatibility`).

## Rationale

The carry question is the whole design. The register-seeded-from-observation
model (O3) is chosen because it is the only shape that satisfies all three
regulated provenances of art. 105 AND the project's carry disciplines at once:
the normal 105.Uno case inherits the stamped-observation cross-check (the same
compounding-error defence `carried-observations-stamp-their-revision` was built
for), while 105.Dos/Tres — values with no filed ancestor — get a first-class,
provenance-tagged home instead of being smuggled through a fake observation or
an untracked profile field. Seeding rather than reading the observation live
keeps one authority (the register) feeding the engine, with the observation as
the verification surface — the same facts-in-register / constants-in-registry
split the bienes-inversión ADR ratified.

In-year apportionment (O5) is not optional polish: art. 104.Uno applies the
percentage "en cada período de liquidación", so the current 100% in-year
deduction is a wrong regulated number for every mixed trader — a silent
OVER-deduction that is the exact mirror of the silent-zero class. Placing it
inside the shared aggregation path is forced by
`one-aggregation-path-pull-equals-calculate`.

Volume authority (O7) follows the lesson that made this campaign stall twice:
a projection that cannot represent the full regulated computation must
reconcile, not replace. The declared annual volume casillas are what the form
files and already drive the registry's definitive-percentage formula; the
ledger rollup earns authority only when it can classify the art-104.Tres
exclusions, and until then it surfaces contradiction.

The advisory-first, promote-on-proof posture for the casilla-44 feed preserves
the scope ADR's Decision 3 and the recorded promotion trigger — this ADR
supplies the missing model, not a shortcut past the proof gate.

## Consequences

- Gain: the LIVA arts. 102-106 provisional→definitive lifecycle becomes a
  tracked, evidence-backed cross-year computation: seeded carry, in-year
  apportionment, settlement regularisation feeding M303 casilla 44 and the M390
  annual field, each figure carrying its provenance.
- Gain: closes BOTH silent defect classes for mixed traders — the silent zero
  (blank casilla 44 / unpopulated volumes at settlement) and the silent in-year
  over-deduction (100% deduction during 1T-3T).
- Gain: unblocks the deferred silent-zero-base rows' named follow-up and, on
  promotion, the bienes-inversión automatic casilla-43 feed.
- Cost accepted: casilla 44 stays operator-confirmable until the end-to-end
  proof lands; the ledger volume rollup ships as advisory reconciliation, not
  authority.
- Difficulty: the AEAT worked-example oracle for the apportionment +
  regularisation chain must be sourced from the Manual práctico IVA and bundled
  before promotion; without it the mechanism stays deferred (no fabricated
  expected values).
- Pitfall: a future agent may seed the register from an UNstamped or
  divergent-stamp observation "to unblock" — the seed gate must stay blocking
  on divergence. A second pitfall: applying the provisional percentage to bases
  instead of cuotas (the form declares full bases; only cuotas apportion).
- Pathway: the register's regime/sector axes are the landing slots for prorrata
  especial and sectores diferenciados; the divergence advisory is the natural
  ratchet toward ledger-derived volumes once exclusion classification exists.
