---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-20-cli-state-architecture-research]]"
  - "[[2026-05-21-profile-uuid-identity-adr]]"
  - "[[2026-05-21-profile-state-aggregate-adr]]"
  - "[[2026-05-21-cli-testimonial-reference]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` adr: `Every operator-facing surface consumes one canonical state read-projection` | (**status:** `accepted`)

## Problem Statement

`overview`, `auth status`, `auth test`, `modelo readiness`, and
`verify` each load a different subset of the state stores and compute
their own view of "the truth". They therefore disagree - verified by
the testimonial cluster
(`[[2026-05-20-cli-state-architecture-research]]`):

- `overview status` reported "no saved drafts" after `calculate` had
  produced work units - `overview` reconstructs state from a
  different store set than `modelo work` writes.
- `auth test` returned an empty active profile while `auth status`
  did not - two readers, two subsets, two answers.
- `auth status` reported `configured: True` next to
  `health_summary: "not configured"` - readiness derived from two
  uncoordinated signals.
- `modelo readiness` said `ready` while `verify` refused with
  `NO_PENDING_OBLIGATION` - two readiness assessments, two answers.

The write side is addressed by the aggregate + repository ADR
(`[[2026-05-21-profile-state-aggregate-adr]]`). This ADR addresses
the read side: **there is no single canonical projection that all
surfaces consume, so every surface re-derives and they drift.**

## Considerations

- **One projection, one producer.** A single function builds the
  operator-facing state view from the aggregates; every surface
  consumes that view and none re-derives.
- **Readiness is computed once.** "Is auth ready", "is this modelo
  ready", "is there a pending obligation" are each computed in one
  place and carried in the projection. `verify` and `modelo
  readiness` consume the same readiness datum - they cannot disagree
  because there is only one.
- **`configured` vs `health` is one model.** Operational readiness is
  a single derived value, not two uncoordinated booleans. The
  certificate-provider case (`configured` true only when a file path
  is recorded) is already fixed in `inspect_operator_auth`; this ADR
  makes one-readiness-model the rule, not a per-surface patch.
- **The projection is pure read.** It never mutates a store. It is a
  function of the aggregates as loaded through their repositories.
- **Typed, not a dict.** The projection is a pydantic model with
  typed sub-records, consistent with the architecture-boundaries
  rule; surfaces read typed fields, not a `dict[str, Any]`.

## Constraints

- No operator-facing surface re-derives state. `overview`,
  `auth status`, `auth test`, `modelo readiness`, and `verify` each
  consume the canonical projection.
- The projection is read-only; building it mutates nothing.
- Each readiness question is computed exactly once and carried in the
  projection; surfaces present it, they do not recompute it.
- The projection is a typed pydantic model, not a flat mapping.

## Implementation

### 1. The projection model

- `OperatorStateProjection` - a typed model with sub-records: the
  active profile and its health, auth readiness (one model covering
  `configured` and `health`), the workspace summary (transactions,
  invoices, modelo work units, drafts), per-modelo readiness, and
  pending obligations.

### 2. The single producer

- `build_operator_state_projection() -> OperatorStateProjection` -
  the one function that assembles the projection by loading the
  profile and workspace aggregates through their repositories and
  computing each readiness value once.

### 3. Rewire the surfaces

- `overview`, `auth status`, `auth test`, `modelo readiness`, and
  `verify` are rewired to call `build_operator_state_projection` and
  read its typed fields. Their bespoke per-surface state assembly is
  deleted.
- `verify`'s obligation gate consumes the projection's
  `pending_obligations`; the `NO_PENDING_OBLIGATION` vs
  `readiness: ready` contradiction disappears because both read the
  same field.

## Rationale

When five surfaces each rebuild "the truth" from a different store
subset, disagreement is not a bug to be patched surface-by-surface -
it is the guaranteed outcome of the design. A single canonical
projection with a single producer makes agreement structural: there
is one view, computed once, and every surface shows the same numbers
because they read the same object. Computing each readiness value
exactly once removes the entire class of "surface A says ready,
surface B says not" contradictions.

## Consequences

- The cross-surface disagreement defect class is closed structurally.
- The per-surface state-assembly code in `overview`, `auth`,
  `modelo`, and `verify` is deleted and replaced by projection reads;
  this is real blast radius, tracked in the shared plan.
- The projection becomes the natural place to add future
  operator-facing state (calendar, agenda, backlog - cf. the apex
  CLI ADR R17) without re-introducing per-surface derivation.
- A change to how a readiness value is computed is made in one place
  and is immediately consistent across every surface.
