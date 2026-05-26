---
tags:
  - '#adr'
  - '#linkage-design-audit'
date: '2026-05-26'
related:
  - "[[2026-05-26-linkage-design-audit-research]]"
  - "[[2026-05-15-linkage-design-audit-research]]"
  - "[[2026-05-17-linkage-design-audit-plan]]"
  - "[[2026-05-18-linkage-design-audit-audit]]"
---

# `linkage-design-audit` ADR: `casilla-values-collapse-projection-strategy` (**status:** `accepted`)

## Status

Accepted (autonomous self-review, 2026-05-26). Grounded against the
companion research note and the in-flight cross-campaign survey
recorded therein. No human-in-the-loop blocker; the staged-path
choice keeps every reversibility door open.

## Problem Statement

`CalculationRevision` currently carries two storage fields for the
per-casilla output payload:

- `casilla_values: Mapping[str, Decimal]` — the original flat
  mapping, persisted on every revision, threaded into
  `derive_calculation_revision_id` to compute the content-addressed
  SHA-256 identity.
- `observations: tuple[CasillaObservation, ...]` — the typed
  envelope carrying formula provenance (added by the dual-write
  campaign at commit `b995da5c8`), default-factory empty for
  backward-compat with revisions persisted before it landed.

The `linkage-design-audit` plan step `P02.S09` calls for
collapsing the flat field into a derived projection over the typed
envelope so the typed observations become the single source of
truth — matching the canonical pattern already established on
`RegistryModeloObservation` (R002) and `RegistryCalculationResult`
(P02.S08, commit `6963600c0`).

The collapse is constrained by content-addressed identity: every
already-persisted revision id was derived against the current hash
payload shape. Any change to the projection must produce a
byte-identical hash for the same logical state, or every catalogue
row mismatches its derived id and the content-addressing invariant
breaks.

The pre-flight pin landed in `P08.S35` (SHA-256
`5b78dd04e614a50fe448439b7fdb843f1e31afe76f9d424d0276866679dee7ca`
for a fully-populated derivation) is the regression anchor; the
decision below must keep this pin stable.

## Decision

Adopt a **staged two-strategy path**:

1. **Stage one (this wave):** keep `casilla_values` as a model field
   on `CalculationRevision`, but route both the constructor's
   id-derivation check and `derive_calculation_revision_id` through
   a single new derivation helper that materialises the
   `{casilla_id: Decimal}` projection from the typed `observations`
   envelope. The flat field becomes a denormalised cache enforced
   equal to the projection at construction time; the typed envelope
   becomes the **logical source of truth** even though both fields
   persist on the wire. Hash domain unchanged — the pinned SHA stays
   stable because the projection produces the same byte string.

2. **Stage two (separate ADR, future cycle):** schedule the full
   wire-shape collapse — drop `casilla_values` as a stored field,
   expose it as a derived `@property` over `observations` (mirroring
   `RegistryModeloObservation`), and migrate every persisted
   catalogue row to the typed-envelope-only payload. Gated behind a
   one-shot data migration ADR and behind one release cycle of
   stage-one running in production.

The staged path was chosen over a one-shot Strategy-B-only landing
because:

- Stage one closes the **P02.S09 logical intent** (typed envelope
  is canonical for derivation) with zero wire-shape risk and zero
  data migration. The 27 construction sites need only `observations=`
  passed alongside `casilla_values=`; both fields land in storage.
- Stage two is properly framed as **what it actually is**: a
  persistence-boundary migration deserving its own ADR with explicit
  upcast semantics for historical rows that lack `observations`.
  Forcing it through P02.S09 conflates two concerns and creates a
  data-migration crisis inside what should be a refactor.
- Reversibility is preserved at every step. If stage two surfaces
  an unanticipated downstream coupling, stage one can run
  indefinitely without harm — the typed envelope is canonical, the
  flat field is a derived cache.

## Consequences

### Stage one (this wave, plan rows `P02.S09` + `P08.S37`)

- `_outputs_for_hash(observations)` helper lands in
  `aeat.domain.modelos._calculation_revision` materialising the
  canonical `{casilla_id: Decimal}` projection. Pure function,
  trivially testable, used by both the model validator and the id
  derivation.
- `derive_calculation_revision_id` signature unchanged at the boundary;
  internally re-routed through the helper when called from the
  constructor (`CalculationRevision._enforce_invariants`). External
  callers that still pass `casilla_values=` keep working unchanged.
- `CalculationRevision._enforce_invariants` re-derives `casilla_values`
  from `self.observations` (when populated) and asserts equality
  with the persisted field. Mismatch raises
  `ModeloValidationError` — turns silent drift into a load-time
  refusal.
- 27 construction sites unchanged for the `casilla_values=` argument;
  the 12+ already passing `observations=` gain the new validator
  guard for free.
- 4 roundtrip suites stay green — fixture shapes unchanged.
- W09.P20 cross-module-import gate stays green — no public surface
  changed.
- The P08.S35 hash-stability pin stays green — projection is
  byte-identical to the current inline projection in
  `derive_calculation_revision_id`.

### Stage two (separate ADR, future cycle)

- New ADR: `casilla-values-flat-field-retirement` — declares the
  data migration semantics, the upcast rule for historical rows
  with no `observations`, and the JSON-schema bump.
- Roundtrip suites re-baseline against the typed-envelope-only
  payload.
- Storage envelopes (encrypted catalogue rows) migrate; one-shot
  upcast on read for rows persisted under stage-one.
- `_outputs_for_hash` helper retained as the canonical projection;
  hash signature unchanged.

## Compliance with established mandates

- **AEAT calculation grounding rule** ("persist typed envelopes, not
  flat scalar mappings"): stage one makes the typed envelope the
  logical source of truth; stage two completes the wire-shape
  alignment. The rule's intent is satisfied at decision time even
  though wire shape carries both fields for one release cycle.
- **Roundtrip discipline rule** ("strict pydantic equality across
  every persistence boundary"): the model validator's
  re-derivation-then-compare turns the flat field into a
  load-time-verified cache; any save/load drift fails at load time
  with `ModeloValidationError`. Hash-stability pin
  (P08.S35) plus the validator assertion together cover both
  directions.
- **Hexagonal direction**: change is confined to
  `aeat.domain.modelos`; no application or adapter import edges
  shift.
- **Anti-tautology**: the helper is pure and exercised by the
  pinned SHA test; if the helper drifts, the pin fails. No
  hand-derived test values introduced.

## Risks accepted

- **One release cycle of dual persistence**: revisions persisted
  during stage one carry both `casilla_values` and `observations`
  on the wire. The validator enforces consistency at load time, so
  drift surfaces immediately, but the storage envelope is larger
  than the eventual stage-two shape. Acceptable for one cycle.
- **Validator strictness on historical rows**: revisions persisted
  before the typed envelope landed (`observations` empty) will
  pass the validator trivially (no projection to compare).
  Acceptable — those rows pre-date the typed envelope and cannot
  be retroactively enriched without a parallel calc replay.

## Plan linkage

This ADR authorises plan steps:

- `linkage-design-audit P02.S09` (collapse `CalculationRevision.casilla_values`
  to derived-from-observations projection at the hash boundary)
- `linkage-design-audit P08.S36` (close-out step naming this ADR)
- `linkage-design-audit P08.S37` (execute stage one against the
  P08.S35 pin)

Stage two is deferred to a separate ADR
`casilla-values-flat-field-retirement` scheduled after one release
cycle of stage one running in production.
