---
tags:
  - '#adr'
  - '#prorrata-especial'
date: '2026-07-07'
modified: '2026-07-17'
related:
  - "[[2026-07-05-cross-period-prorrata-adr]]"
  - "[[2026-07-01-iva-complexity-hardening-scope-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]"
  - '[[2026-07-10-prorrata-especial-research]]'
---

# `prorrata-especial` adr: `Prorrata especial per-input classification (LIVA arts 103.Dos/106): 100/0/prorrata deduction and the +10% mandatory-especial advisory` | (**status:** `accepted`)

## Problem Statement

The accepted `cross-period-prorrata` ADR shipped in-year apportionment for prorrata
**general** only: the shared ledger IVA aggregation
(`application/aggregation/_iva_ledger.py`, `_active_general_prorrata_apportionment`)
multiplies *every* deducible cuota by one whole-entity general percentage. Under
prorrata **especial** (LIVA art. 106) that is a wrong regulated number for a mixed
trader who has elected or is obliged into especial: art. 106 does not apply one
percentage to the whole soportado — it classifies each input cuota by its **use**
and deducts accordingly. Verbatim from the bundled consolidated LIVA
(`ley-37-1992.html`, `#a106`), art. 106.Uno:

- regla 1.ª — cuotas on goods/services used **exclusively** in operations that
  originate the right to deduct: deducted **in full** (100%);
- regla 2.ª — cuotas on goods/services used **exclusively** in operations that do
  not originate the right: **no deduction** (0%);
- regla 3.ª — cuotas on goods/services used **only in part** in deductible
  operations: deducted at the art. 104.Dos-and-following **general** percentage,
  following the art. 105 procedure.

The compute substrate already has the primitives — `InputClassification` (StrEnum:
exclusive-deductible / exclusive-non-deductible / common-use),
`classify_input_deduction`, `_deductible_percentage_for`, and `is_especial_mandatory`
(the art. 103.Dos.2 +10% gate, driven by
`PRORRATA_ESPECIAL_MANDATORY_MULTIPLE = Decimal("1.10")` in `core/external_constants.py`)
— and the register regime enum (`ProrrataRegisterRegime`) already carries the
`especial` member. What is missing is the *wiring*: nothing carries a per-input
use-classification signal from the ledger into the apportionment, so an especial
bucket is silently apportioned as if it were general; and the art. 103.Dos.2
mandatory-especial +10% comparison never fires. The parent ADR named this exact
deferral: "prorrata especial per-input apportionment and the art. 103.Dos.2 +10%
mandatory-especial comparison advisory (needs especial to exist)."

## Considerations

- Art. 106 classification is a per-**input** *use* fact the taxpayer asserts about
  each purchase; it is not derivable from the cuota amount, from the general
  percentage, or from the IVA category alone. It must be an operator-supplied signal
  persisted with the ledger row (`sensitive-financial-data-secure-storage-only`
  applies to the row, not to the classification, which is metadata).
- The substrate is stable and complete for the math (the `2026-05-12` accepted ADR):
  this feature *consumes* `classify_input_deduction` / `_deductible_percentage_for` /
  `is_especial_mandatory` and does not re-open them (`no-tautological-calculation-tests`
  — the classification routing is tested against an AEAT worked example, not against
  the substrate's own arithmetic).
- The regla-3.ª common-use percentage is the *same* art. 104.Dos general percentage
  the register already resolves and the general path already applies. Especial reuses
  the general apportionment for its common-use slice and adds only the 100%/0%
  exclusive branches — it is an extension of the landed general path, not a parallel
  one (`one-aggregation-path-pull-equals-calculate`,
  `composition-service-no-parallel-write-path`).
- The art. 103.Dos.2 +10% test compares the *whole-year* deductible total under the
  general rule against the deductible total under especial; it is therefore a
  settlement-time (4T/0A) comparison, only computable once both regime totals for the
  ejercicio exist — which requires the especial computation this ADR provides.
- Regime selection is a filed taxpayer decision (art. 103.Dos.1 opt-in, or the
  art. 103.Dos.2 obligation): the app must *surface* the obligation, never silently
  switch a taxpayer's regime between years.

## Considered options

**D1 — Where the per-input classification signal comes from.**

- **(a) A typed per-transaction `InputClassification` field on the ledger row
  (CHOSEN).** Operator-declared at ledger entry for buckets under especial; persisted
  with the transaction. Matches the substrate's own `ProrrataInputDeduction` /
  `classify_input_deduction` shape. Pro: art. 106 is genuinely a per-input use fact;
  the row is where it lives. Con: a new typed field on the transaction model (a shared
  surface — see footprint).
- (b) Derive classification from the existing free-text `prorrata_reference` pointer
  (REJECTED). The reference points at a legal basis, not a use-classification; the
  three art. 106 uses are orthogonal to which article applies. Overloading it re-creates
  an untyped signal the codebase's typing discipline forbids.
- (c) Operator-declared per registry binding rather than per row (REJECTED). Use is a
  per-purchase fact, not a per-casilla fact; a binding-level flag cannot represent a
  bucket with mixed exclusive-deductible and common-use purchases.

**D2 — How the apportionment routes per-input.**

- **Regime-aware apportionment inside the one shared aggregation (CHOSEN).** When the
  register entry regime is `especial`, `_active_general_prorrata_apportionment` (renamed
  to reflect regime-awareness) applies `_deductible_percentage_for` per candidate:
  exclusive-deductible → 100%, exclusive-non-deductible → 0%, common-use → the general
  percentage. The general-regime path is byte-identical to today; non-prorrata
  taxpayers unaffected. The applied classification and percentage ride on the binding
  value provenance (`binding-values-carry-provenance`).
- A second especial-only resolver/aggregation path (REJECTED) —
  `one-aggregation-path-pull-equals-calculate` and the parent ADR's single-path
  constraint forbid it.

**D3 — When the art. 103.Dos.2 +10% mandatory-especial advisory fires.**

- **Settlement-time non-blocking advisory (CHOSEN).** At 4T/0A, once the year's
  general-regime and especial-regime deductible totals are both computable, call
  `is_especial_mandatory`; if the general-regime deductible cuotas exceed the especial
  total by ≥10% (`PRORRATA_ESPECIAL_MANDATORY_MULTIPLE`), emit an `info`/advisory
  `Notice` naming that especial is obligatory for the ejercicio (art. 103.Dos.2), with
  the two totals on `Notice.context`. Advisory, not blocking: the taxpayer may already
  be under especial; the classification data may be incomplete; and the regime switch
  is a filed decision (`cli-notices-are-the-only-diagnostic-channel`,
  `no-silent-under-declaration`).
- Blocking refusal on the +10% breach (REJECTED) — would refuse a legitimately
  in-progress filing whose especial election has not yet been recorded.

## Constraints

- Parent stability: the general/especial/sectoral compute substrate (`2026-05-12`
  ADR, accepted) and the `cross-period-prorrata` in-year general apportionment
  (accepted, landed) are both stable and consumed, not re-opened. This ADR concretises
  one of that ADR's named deferrals; it does not contradict it.
- No fabricated regulated values: the +10% multiple stays the registry/corpus-grounded
  `PRORRATA_ESPECIAL_MANDATORY_MULTIPLE` constant; there is no default classification —
  an especial bucket with an unclassified deducible input surfaces an advisory, never a
  silent assumed use (`no-silent-under-declaration`).
- Legal grounding: art. 103 and art. 106 are present verbatim in the bundled
  consolidated LIVA (`ley-37-1992.html`, `#a103` / `#a106`) but are **not yet** distinct
  entries in `legal/iva.toml` (only art. 102/104/105 are). The implementation MUST
  author the art. 103 and art. 106 legal entries with `corpus_ref` into the bundled
  file and a `required_text` cross-check (`registry-calculation-legal-grounding`,
  `legal-grounding-verifies-bundled-authoritative-corpus`).
- Verification: the 100%/0%/common routing and the +10% advisory are proven against an
  AEAT Manual práctico IVA worked example that exercises all three art. 106 reglas,
  never numbers hand-computed from the substrate (`no-tautological-calculation-tests`,
  `verification-grounding-needs-oracle-evidence`).
- Roundtrip: the new per-transaction classification field participates in the ledger
  row save/load/equality roundtrip plus an anti-tautology proof
  (`aeat-roundtrip-discipline`).

## Implementation

A typed `input_classification` axis (the existing `core` `InputClassification` StrEnum)
is added to the ledger transaction / IVA ledger candidate, operator-declared and
meaningful only for buckets whose register regime is `especial`. The shared ledger IVA
aggregation becomes regime-aware: for a `general` entry it applies the whole-entity
percentage exactly as today; for an `especial` entry it routes each deducible candidate
through `_deductible_percentage_for` (100% exclusive-deductible, 0%
exclusive-non-deductible, the art. 104.Dos general percentage for common-use), carrying
the applied classification + percentage on the binding value provenance. At settlement,
a pure comparison over the year's general-vs-especial deductible totals feeds
`is_especial_mandatory`; a breach raises an advisory `Notice` (art. 103.Dos.2). The
art. 103 / art. 106 legal entries are authored into `legal/iva.toml` grounded in the
bundled corpus, and any M303 especial-classification casilla/binding metadata is
registry-declared. The `PRORRATA_REGULARIZACION` source disposition and the casilla-44
feed are unchanged by this ADR — especial changes *how the deducible side is
apportioned*, feeding the same regularización mechanism the parent ADR built.

## Rationale

Especial is the one place the parent ADR's single general percentage is legally wrong,
and the substrate already carries every primitive to do it right — the gap is purely
wiring a per-input signal and routing on it. Choosing a typed per-row classification
(D1a) matches art. 106's per-input nature and the substrate's own model, and keeps the
signal auditable; extending the one shared aggregation (D2) rather than forking it obeys
the single-path rule and makes non-especial taxpayers byte-identical. The +10% advisory
(D3) is settlement-time and non-blocking because especial obligation is a comparison
result that must inform, not brick, an in-progress filing — the same advisory-first
posture the parent and scope ADRs took for casilla 44.

## Consequences

- Gain: a mixed trader under especial deducts each input at its lawful rate
  (100% / 0% / general %) instead of a single wrong whole-entity percentage; the
  art. 103.Dos.2 obligation is surfaced instead of silently missed.
- Gain: reuses the landed cross-period register, seeding, and settlement regularización
  unchanged — especial is an apportionment-branch extension, not a new mechanism.
- Cost accepted: especial requires per-input operator classification; an especial bucket
  with unclassified inputs is advisory-flagged, not auto-resolved.
- Difficulty: the AEAT worked-example oracle must exercise all three art. 106 reglas and
  the +10% comparison; without it the routing stays unproven (no fabricated expected
  values).
- Pitfall: a future agent may apply the especial classification to bases; only *cuotas*
  apportion (the form declares full bases). A second pitfall: treating the +10% advisory
  as blocking and refusing legitimate not-yet-elected filings.
- Pathway: the classification axis and regime-aware aggregation are the substrate that
  `prorrata-sectores-diferenciados` extends to per-sector routing.

## Implementation footprint

Files the implementation will touch (for wave-clustering; see the ADR-vs-ADR overlap
report):

- `src/cadrumo/domain/transactions/_models.py` — add the typed `input_classification`
  axis to the ledger transaction. **SHARED with `prorrata-sectores-diferenciados`
  (sector reference) and `prorrata-art104-tres-exclusions` (exclusion tag).**
- `src/cadrumo/application/aggregation/_iva_ledger.py` — make
  `_active_general_prorrata_apportionment` regime-aware (especial 100/0/general
  routing). **SHARED with `prorrata-sectores-diferenciados` (per-sector routing) and
  `prorrata-art104-tres-exclusions` (annual-rollup exclusion filtering) — hottest
  shared surface.**
- `src/cadrumo/application/calculations/_prorrata_regularizacion.py` — the settlement +10%
  mandatory-especial advisory builder. **SHARED with `prorrata-art104-tres-exclusions`
  (divergence/rollup advisories live here).**
- `src/cadrumo/domain/iva/_prorrata.py` — consume existing `classify_input_deduction` /
  `_deductible_percentage_for` / `is_especial_mandatory` (read-mostly; maybe an especial
  per-input apportionment helper). **SHARED (additive) with all three sibling ADRs.**
- `src/cadrumo/domain/prorrata_register/__init__.py` — possibly an especial
  classification-complete signal on the entry. **SHARED with
  `prorrata-sectores-diferenciados` and `prorrata-art105-cinco-interrupted`.**
- `src/cadrumo/_data/registry/aeat/legal/iva.toml` — new `[legal."ley-37-1992:art-103"]`
  and `[legal."ley-37-1992:art-106"]` entries. **SHARED (additive, distinct blocks)
  with all three sibling ADRs.**
- `src/cadrumo/_data/registry/aeat/modelos/303/**` — especial classification casilla /
  binding metadata. **SHARED with `prorrata-sectores-diferenciados` and
  `prorrata-art104-tres-exclusions`.**
- CLI ledger surface (`entrypoints/cli/.../_ledger.py` or a `prorrata` verb group) —
  operator declares the per-input classification. **SHARED with
  `prorrata-sectores-diferenciados` and `prorrata-art104-tres-exclusions`.**
- `src/cadrumo/core/external_constants.py` — `PRORRATA_ESPECIAL_MANDATORY_MULTIPLE` already
  exists; read-only, no write.
