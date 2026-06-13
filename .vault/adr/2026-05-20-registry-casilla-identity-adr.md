---
tags:
  - '#adr'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - '[[2026-05-20-registry-casilla-identity-research]]'
  - '[[2026-05-20-branch-reconciliation-audit]]'
---



# `registry-casilla-identity` adr: `segment-scoped casilla identity and Diseño-completeness gate` | (**status:** `accepted`)

## Problem Statement

The registry identifies a casilla by its bare five-digit AEAT number.
`CasillaDefinition` (`src/aeat/domain/calculations/registry/_schema.py`)
carries both `id` and `number`, and every authored modelo fragment sets
`id == number`. The registry validator
(`src/aeat/domain/calculations/registry/_validate.py`) hard-rejects two
casillas that share an `id`, so the bare number is, in practice, a
globally unique key within a modelo revision.

This assumption is false for multi-segment AEAT modelos. The official
Modelo 200 Diseño de Registros reuses the same five-digit casilla number
across record segments — `DP200010` (Estado de cambios patrimonio neto),
`DP200014` (Liquidación), `DP200032`, `DP200042`, `DP200DID` — with a
different meaning in each. Casilla `00562` is "Cuota íntegra" in the
Liquidación segment and "distribución de dividendos" in the ECPN segment.

Because the model cannot hold two casillas numbered `00562`, the Modelo
200 author could declare only one occurrence per number. The Liquidación
cuota-chain casillas — `00562` cuota íntegra, `00558` tipo de gravamen,
`00552` base imponible liquidación, `00611` cuota diferencial — were
never authored; the registry kept the ECPN occurrences. Modelo 200
nonetheless loads green: snapshot-build validation checks duplicate-id
and `semantic_role` consistency but never checks completeness against the
AEAT Diseño, so a casilla absent from the registry is invisible. A tax
form's filing-grade calculation chain is silently missing and no gate
fails. This blocks the Modelo 200 formula port and will recur for Modelo
220 and the multi-segment fichero-BOE forms.

## Considerations

- **The bare number is the de-facto join key of the whole registry
  graph.** Formula `target` and `expression` args (`{ casilla = "00592" }`),
  export-layout casilla bindings, cross-modelo relations, verification
  expectations, extraction profiles, and the Modelo 100 renta routing
  table all reference casillas by bare number. Any identity change has a
  graph-wide blast radius — though the four-agent blast-radius swarm
  confirmed every current reference site is single-segment today; only
  Modelo 200 is affected.
- **The majority of modelos are single-segment.** Roughly 25 of 26
  modelos have globally unique casilla numbers and must not pay a
  migration cost for a defect that only multi-segment forms exhibit.
- **The AEAT source already carries the disambiguator.** The Modelo 200
  Diseño workbooks are multi-sheet, one sheet per record segment
  (`DP200010`, `DP200014`, ...), already parsed by `_record_design.py`
  into `RecordDesignSheet`. A casilla's true identity is the pair
  `(record segment, number)`.
- **The defect mechanism is missing data, not silent overwrite.** The
  duplicate-id validator never fired — the second `00562` was simply
  never authorable, so never authored. The fix must therefore make the
  missing casillas both *declarable* (identity) and *required*
  (completeness).
- **Governing accepted ADRs.** `2026-05-18-schema-hardening-adr` mandates
  the strict-pydantic discipline of the `ValidatedRegistryAuthority` load
  surface and hard-error-at-snapshot-build enforcement;
  `2026-05-19-spanish-stem-terminology-authority-adr` mandates Spanish
  stems for tax-domain identifiers; `2026-05-19-modelo-registry-fragment-
  architecture-adr` governs the per-modelo fragment layout.
- **Options evaluated** (full evaluation in the research artifact):
  - *A1 — composite `id`* (segment-prefixed string id): forces a
    corpus-wide rewrite of every casilla fragment and every reference
    site.
  - *A2b — keep `number`, add an optional `segmento` field, make
    `(segmento, number)` the uniqueness key*: purely additive;
    single-segment modelos leave `segmento` unset and are untouched.
  - *A3 — semantic slug as `id`*: corpus-wide rewrite, and collides
    conceptually with the `semantic_role` atom from the schema-hardening
    ADR.
  - For the completeness gate: *B3 — an extraction-derived, checked-in
    Diseño-completeness manifest, hard-gated at snapshot build* — versus
    parsing the Diseño live at load time (slows every snapshot build).

## Constraints

- The change must be **additive**: single-segment modelos must validate
  unchanged with `segmento` unset, so the field is `str | None` defaulting
  to unset.
- New and amended models must hold the strict / frozen / `extra="forbid"`
  discipline of the registry load surface.
- The new field name and any new identifiers must use Spanish stems —
  `segmento`, not `segment`.
- Snapshot build must stay fast: the completeness gate must not parse the
  corpus Diseño workbooks on the load path.
- Per the schema-hardening rollout discipline, all 26 modelos must remain
  valid throughout the rollout; the completeness gate flips to hard-error
  per modelo only once that modelo's manifest exists and its declared
  casillas satisfy it.
- No live AEAT write surface is touched; this is registry-data and
  validation only.

## Implementation

**Decision A2b — segment-scoped casilla identity.**

- Add an optional field `segmento: str | None = None` to
  `CasillaDefinition` in `src/aeat/domain/calculations/registry/_schema.py`,
  carrying the AEAT record-segment identifier (e.g. `"DP200014"`) for
  multi-segment modelos and left unset for single-segment modelos.
- The casilla uniqueness invariant enforced by the registry validator
  changes from "`id` unique" to "`(segmento, number)` unique within a
  modelo revision". The generalised check subsumes the current behaviour:
  with `segmento` unset, `(None, number)` uniqueness is exactly today's
  bare-number uniqueness.
- `id` remains the stable within-revision handle. For multi-segment
  casillas it is composed to stay globally unique within the revision
  (carrying the segment); for single-segment casillas it continues to
  equal `number`. The precise id-composition and the
  reference-resolution rule (how a formula or export arg selects the
  intended segment occurrence of a reused number) are Plan-phase
  mechanics, constrained by this ADR to preserve single-segment
  references unchanged.

**Decision B3 — Diseño-completeness gate.**

- For each modelo, a Diseño-completeness manifest enumerating the
  expected `(segmento, number)` casilla set is derived from the corpus
  AEAT Diseño de Registros and checked into the registry as reviewed
  data.
- `RegistryValidator` gains a hard-error gate at snapshot build that
  compares the modelo's declared casillas against its manifest; a missing
  or mismatched casilla fails the load. The gate is **fail-closed**: a
  missing manifest is itself an error, not a skip.
- Manifest generation is an off-load-path step; an audit-cadence
  re-verification regenerates manifests from the corpus to surface drift
  in CI without slowing snapshot build.

**Sequencing.** A2b and B3 land together. A2b makes the missing Modelo
200 Liquidación casillas declarable; B3 makes them required. Once Modelo
200's manifest exists, the completeness gate stays red until the
Liquidación cuota chain is registered under `segmento = "DP200014"` — so
the fix is self-enforcing.

## Rationale

A2b is the only option that is purely additive: the ~25 single-segment
modelos pay zero migration cost because `segmento` defaults unset and
`(None, number)` uniqueness reproduces today's behaviour exactly. A1 and
A3 both force a corpus-wide rewrite of every casilla fragment and every
reference site; A3 additionally overloads the identity slot with semantic
meaning that the schema-hardening ADR already assigns to `semantic_role`.
The AEAT Diseño already carries the record segment as a first-class
structure, so `(segmento, number)` is the form's own identity model, not
an invention.

B3 keeps snapshot build fast — the manifest is precomputed reviewed data,
not a live parse of multi-megabyte Diseño workbooks — while making the
real failure mode (a silently missing casilla) a hard gate. The
fail-closed posture and off-load-path re-verification follow the
schema-hardening ADR's stance that audit-only mechanisms have already
failed at this scale and that hard-error at the load surface is the only
enforcement the codebase reliably sustains.

Landing A and B together is deliberate: identity without completeness
would let the M200 gap persist undetected; completeness without identity
could not be satisfied because the casillas would remain undeclarable.

## Consequences

- Modelo 200 — and, prospectively, Modelo 220 and the multi-segment
  fichero-BOE forms — becomes representable. The M200 Liquidación
  cuota-chain casillas can be registered under `segmento = "DP200014"`,
  unblocking the Modelo 200 cuota formula port.
- The completeness gate will report Modelo 200 as **failing** once its
  manifest lands and until the Liquidación casillas are registered. This
  is intended: the defect becomes loud instead of silent.
- A one-time migration authors Diseño-completeness manifests for the 26
  modelos. Per the schema-hardening rollout discipline the gate goes
  hard-error per modelo only after that modelo clears its manifest.
- Formula, export, and relation reference resolution must become
  segment-aware for multi-segment modelos — a Plan-phase concern scoped
  by this ADR to leave single-segment references untouched.
- Residual risk: manifest drift if a corpus Diseño is updated without
  regenerating the manifest. Mitigated by the off-load-path audit-cadence
  re-verification, which fails CI on divergence.
- Follow-on: this ADR does not itself author the M200 casillas or the
  manifests; those are Plan/execution work that depends on this decision.

## Amendment (2026-05-20): completeness gate refocused to calculation-completeness

During execution of the implementing plan a design tension surfaced in
decision B3 as originally written. B3 named the gate a
"Diseño-completeness" gate — declared casillas checked against the full
AEAT Diseño de Registros. Modelo 200's Diseño is a 75-segment form of
several thousand casillas, the large majority of which are
accounting-statement data-entry fields that feed no formula. A
load-blocking gate keyed on full-Diseño coverage would fail every modelo
whose registry is not yet exhaustively backfilled (all of them),
conflating data-entry completeness with calculation correctness. The
opposite reading — a drift-only gate — would not have caught the very
M200 defect this ADR exists to fix.

Measured against the project mission — verified, legally-grounded modelo
calculations through a cross-connecting calculation engine — B3 is
refined as follows. This amendment supersedes the wording of B3 in
Considerations, Constraints, Implementation, Rationale, and Consequences
above wherever the two conflict; decision A2b is unchanged.

- **The load-blocking gate enforces calculation-completeness, not
  Diseño-completeness.** For each modelo it verifies that every casilla
  in the modelo's *calculation closure* — formula targets, their
  transitive casilla inputs, binding and relation endpoints, and
  verification-expectation operands — is (1) present in the registry,
  (2) at the correct `(segmento, number)` identity, and (3) carrying its
  `legal_refs` and `source_refs`. This is the casilla set the
  cross-connecting calculation engine traverses; a gap here is a
  calculation-correctness defect, which is exactly the M200 failure mode.
- **The calculation-completeness manifest** enumerates that closure. It
  is derived from the AEAT Diseño *intersected with* the modelo's
  calculation surface — Diseño-authoritative on each casilla's segment,
  number, and label, but bounded to what the engine needs. A calculation
  closure is bounded, so a manifest is tractable to author and a modelo
  can clear it without a full-form backfill.
- **Gate semantics** are `manifest-required ⊆ declared` plus the identity
  and legal-grounding checks above — not `declared == manifest`. A
  declared casilla absent from the calculation manifest (a pure
  accounting-statement field) is not a failure.
- **Full-Diseño coverage is retained as an off-load-path advisory
  coverage report**, not a build gate. The Diseño-extraction machinery
  built for B3 is repurposed to inventory form-level data coverage and
  surface known gaps without redding the load.

Consequence: Modelo 200 clears the calculation-completeness gate once its
cuota-chain casillas are registered (done in the implementing plan's
Modelo 200 phase); the build stays green throughout rollout; and the
gate still hard-fails the silently-dropped-calculation-casilla defect
class. The implementing plan and the gate code are updated to this
refined B3.
