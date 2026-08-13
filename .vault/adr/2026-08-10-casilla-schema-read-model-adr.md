---
tags:
  - '#adr'
  - '#casilla-schema'
date: '2026-08-10'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:7f10dd6ecbde0a95b5bb61dfb3c9001395420a1716fb75543a4539d9605eda7a'
related:
  - "[[2026-08-10-casilla-schema-research]]"
  - "[[2026-05-21-state-read-projection-adr]]"
  - "[[2026-06-10-cli-envelope-notice-standardisation-adr]]"
---

# `casilla-schema` adr: `one modelo work review read-model in application/modelo` | (**status:** `accepted`)

## Problem Statement

Every surface that reviews a modelo work unit re-derives its own view of schema, values, findings, readiness and blockers, and the derivations disagree (`2026-08-10-casilla-schema-research`, Q1-Q5 and B-05/B-08). A TUI review screen is next in line to become the sixth re-derivation. A single assembled, typed read record is needed, with an owner layer, before that screen is built.

## Considerations

- The record must join registry schema, persisted calculation revisions, verification reports and cross-period state; the persisted stores are reachable only from the application layer (research: layered-contract finding).
- `adapters -> application` is the sanctioned consumption direction; TUI screens already import `application.flows`.
- The accepted `2026-05-21-state-read-projection-adr` mandates one canonical read projection per readiness question; `application/overview/_pipeline_health.py` currently violates it (research, B-08).
- The three value-origin layers (declared / concrete / realised) carry signal in their disagreement and must not be collapsed (research, Q4).
- The findings join is thin: 8 of 34 construction sites populate `casilla_id` (research, envelope inventory).
- A ratio-token refusal exists on one payload with a denominator-trust rationale (research, Q2).

## Considered options

- **Domain-owned record** - rejected: domain is barred from application-layer repositories and persisted state by the import-linter contracts.
- **Entrypoints-owned view assembly** - rejected: nothing inward can consume it; the stranded `_BINDING_SOURCE_TO_READINESS` dict shows how an entrypoints-owned vocabulary rots unreused.
- **TUI-only view-model injected by the entrypoint** - rejected: duplicates the assembly for the CLI, and cross-period attribution serves the agent-operated CLI equally.
- **Application-owned record in `application/modelo`, consumed by CLI and TUI alike** - chosen.

## Constraints

- Depends on the canonical derivations ADR (`2026-08-10-casilla-schema-canonical-derivations-adr`) for the joins it embeds, and on the blocker-spine ADR for the `blocked_by` vocabulary; the record must not ship before those land or it hard-codes today's fragmented answers.
- Revision identity is law-determined: the producer resolves via `authority.snapshot(...)` and only asserts equality against a stored stamp.
- `resolve_calculation_binding_channels` is private to `application/modelo`; facade promotion is a precondition of the record consuming it.
- Numeric N-of-M progress is RULED PERMITTED by the owner (2026-08-10): counts render only against the named manifest denominator, never as a bare percentage; a revision without a manifest renders the UNDEFINED state (not measurable), never zero. Field names must not use the ratio tokens the existing payload gate forbids.

## Implementation

One frozen pydantic model `ModeloWorkReview` with a single producer `build_modelo_work_review(bucket_id, modelo, filing_year, period)`, exported through the `application.modelo` facade. Per-casilla rows carry: identity (id, number, segmento, nullable official reference), section path, label, data type and constraints (read from the registry `CasillaDefinition.data_type` and `CasillaConstraints`); the three origin layers side by side (declared `InputKind`; concrete binding channel or formula reference, relation-fed slots resolved through the promoted consumption index; realised `ModeloValueKind` plus value) with a derived origin-anomaly flag; the three-state official-box classification; grounding (`legal_refs`, `source_refs`, `formula_id`); and spine-typed `blocked_by` references. Record-level fields: lifecycle state, verification outcome (nullable, never collapsed into lifecycle), typed progress state, findings with populated `casilla_id` (the 26 unset construction sites across 18 files are swept as part of this work), and blockers.

Field pins, so a cold implementer invents nothing: the nullable official reference is DERIVED from the canonical classification (the box number for a fixed-width slot, the dictionary path for an xml slot, `None` when the classification is REPRESENTED_VIA_BINDING or UNDEFINED) - never from `export_refs`, which understates on 7 revisions per the research. The origin-anomaly flag is a closed two-member enum: BROKEN_CALCULATION_CHAIN (declared computed, realised empty) and OPERATOR_OVERRIDE (declared bound, realised literal); `None` otherwise - exactly the two signals the research names, no invented third. The progress state is a core four-member StrEnum (complete, in_progress, blocked, undefined). Lifecycle state is `CalculationRevisionState`, verbatim. `blocked_by` uses ONE `BlockerRef` shape at both grains - spine axis, native code, optional facts map - with the record-level list being the union and the per-casilla list the attributed subset. The producer's failure contract: an unresolvable `(modelo, filing_year, period)` or unknown bucket refuses with an instructive error; a resolvable target with no persisted revision returns a record whose realised layer is empty and whose verification outcome is `None` - absence renders, it does not raise.

The CLI registers a `modelo.work.review` envelope wrapping the same model; advisories ride the shared `Notice` spine with machine facts in `Notice.context`. Progress counts render per the owner ruling: count fields named without the seven forbidden ratio tokens, plus a denominator field whose value identifies the completeness manifest and its revision. `modelo.requires` is widened, not replaced: its classifier gains buckets for `previous_filing` / `relation_prefill` / `live_observation`, reads primary plus alternate bindings, and surfaces unbucketed sources as an explicit advisory. The pipeline-health surface is re-pointed to read the persisted verification outcome so INCOMPLETE is visibly distinct from never-verified, restoring `2026-05-21-state-read-projection-adr`, which this record reaffirms rather than supersedes.

## Rationale

Application ownership is the only placement the layer contracts permit that both CLI and TUI can consume, and it is the same discipline the accepted state-read-projection ADR already established at profile grain - reaffirming it and fixing the one violating surface is strictly cheaper than amending an accepted record to bless drift. Keeping the three origin layers separate is what preserves the two operator-critical signals the research names. Envelope-first (rather than TUI-only) attribution keeps the agent-operated CLI first-class.

## Consequences

Gains: one truthful record; the TUI review screen becomes a rendering exercise; readiness and verification stop disagreeing by construction. Costs: a facade promotion, a findings-attribution sweep, and the record is blocked behind two sibling ADRs - by design, so it cannot fossilise today's duplicates. The owner ruled (2026-08-10) that N-of-M counts are permitted under the named-denominator guardrails, so the progress column ships with the record rather than waiting. Pitfall to watch: the record must not grow write-side behaviour; it is pure read.

**Amendment, 2026-08-13 - the review screen's location is transitional, and its exit is now an owned plan row.** This record's W04.P10 delivered the screen into `src/cadrumo/adapters/inbound/tui/`, which is not where a Textual surface belongs: `2026-08-11-tui-architecture-adr` D10 designates `src/cadrumo/entrypoints/tui/` as the sole production TUI root and D12 requires `cadrumo.adapters.inbound.tui` deleted without a compatibility facade. The location was sanctioned only as a sequencing compromise by `2026-08-12-casilla-schema-s34-tui-architecture-curation-audit`, conditional on later absorption.

The defect that amendment closes was structural rather than a judgement call: **no step in the tui-architecture plan named this screen**, so the plan's own completion criterion demanded its removal while no row owned the move. That is how a plan and a tree drift apart while both look green. `W04.P10.S104` is now inserted in that plan - beside the peer relocations and ahead of the relocation-parity proof - to move the screen and its tests to `cadrumo.entrypoints.tui.modelo.view` as a read-only consumer of the public `application.modelo` facade and delete the legacy screen, exports and locale references in the same change. The interface ADR's precondition for creating that destination is satisfied: this campaign published `ModeloWorkReview` and closed on 2026-08-13.

This record rules nothing about frontend topology, which is not its authority. It records only that the screen it produced is on loan to the legacy package until `W04.P10.S104` lands, and that the obligation is tracked by a row rather than by prose. A correction is noted for the next reader: an earlier version of this amendment declared the placement permanent and the relocation unreachable, on a mistaken reading that the TUI campaign had been cancelled. It had not been.
