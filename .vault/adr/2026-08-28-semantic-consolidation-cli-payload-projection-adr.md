---
tags:
  - '#adr'
  - '#semantic-consolidation'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:d989fbe8319b7e4da7b09c8c7ca19afce5d46cf0dfdfc726a957f587dd418181'
related:
  - "[[2026-08-28-semantic-consolidation-research]]"
---

# `semantic-consolidation` adr: `CLI payloads are projections, never independent declarations` | (**status:** `accepted`)

## Problem Statement

116 payload classes under `entrypoints/cli/` declare a field set identical to a model
in `application/`, `domain/` or `adapters/`. A census read 114 of them and classified
each by the DIRECTION of its divergence rather than by whether it differed at all,
because the direction turns out to decide the fix.

Roughly 67 are equivalent projections: the same constraints on both sides, differing
only in the repo-wide wire loosening (`tuple` to `list`, `date`/`datetime` to `str`,
nested model to nested payload). Those are not the problem.

The remaining ~46 diverge, and they diverge in both directions at once. Around 35 DROP
a constraint the canonical model enforces. Around 11 ADD a constraint the canonical
model lacks.

## Findings

The dropped constraints are not cosmetic. The severe cases are invariants, not bounds:

`VerificationReportPayload` omits the model_validator enforcing content-addressed id
derivation and the `granted_verificado_completo` bidirectional invariant.
`ModeloReconciliationDiffPayload` omits `_enforce_value_diff_grounding`, which requires
a non-header diff to carry non-empty `legal_refs` and `source_refs` -- a grounding
invariant that `aeat-calculation-grounding` requires to reach the operator surface.
`M210IncomeClassificationPayload` omits the registry-membership validator on
`official_tipo_renta_code`, `ge=0` on gross income and `ge/le(0, 1)` on the applicable
rate. `ProrrataEntryPayload` omits an exact-schema-version field validator and a
cross-field coupling rule. `LedgerHistoryEventPayload` omits `_enforce_derived_id`.

The added constraints are the more consequential finding, because each one is the CLI
INVENTING BUSINESS LOGIC. `RatiosEligibleRowPayload` bounds a deduction ratio into
`[0, 1]` with a validator the canonical model does not carry.
`LiveIvaAuthOutcomePayload` imposes `pattern=r"^sha256:[0-9a-f]{12}$"` on a field the
canonical declares as bare `str | None`. `DataInventoryCasillaPayload` requires
non-empty `legal_refs` and `source_refs` where the canonical is a plain frozen
dataclass carrying no validators at all -- so the only validation of that record
anywhere in the system lives in the CLI. `WorkUnitHistoryEventPayload` types `actor` as
`BucketActorLabel` while the canonical defaults `actor` to `""`, a value the CLI's own
type would reject.

Every one of those invented constraints is, on its face, CORRECT. A count cannot be
negative; a ratio belongs in `[0, 1]`; a digest has a format. That is precisely what
makes them dangerous rather than harmless: an author found a real rule and put it in
the layer that cannot own it, so the backend can still produce a value its own operator
surface would refuse.

`ConfigResetSummaryPayload` shows the endpoint. It carries `_validate_summary`
duplicated verbatim from its source. The two agree today, which is exactly how the
arrangement reads as acceptable and exactly how it drifts tomorrow.

A fourth population sits beside the constraint census and is not counted in it: CLI
validators that reimplement logic independently, matching none of the sanctioned shapes
and not reducible to a single added `Field` constraint. Confirmed instances include
`_overview_payloads.py:87`, `:132`, `:231`, `:296`, `:392`,
`_config_descendiente_payloads.py`, `_modelo_payloads.py:396` and `:852`, and
`_config/_check_payloads.py:92`. These are the sharpest form of the CLI owning business
logic, and they are unmeasured -- the field-set detector cannot see them, because a
reimplemented validator does not change the field set.

## Constraints

The operator directive governing this decision: **the CLI does not invent business
logic. It is a consumer of the backend, never a capability inventor.** This is
load-bearing rather than stylistic, because a rule the CLI owns is a rule no other
consumer of the same backend inherits.

`2026-06-05-modelo-work-revision-cli-decomposition-adr` already rules that revision
commands are thin transports over application facades. Nothing in the accepted corpus
sanctions an independently-declared payload model.

## Considered options

**Delete the payload layer and emit canonical models directly.** Rejected: the wire
loosening is real and necessary. A `date` must serialise, a `tuple` must become a JSON
array, and `aeat-cli-contract` requires a stable registered output schema per command.

**Keep payloads and make them match by hand.** Rejected: this is the current state.
114 hand-matched pairs produced 46 divergences, and a "make them match" pass would pick
a direction per field without deciding which layer OWNS the rule -- silently stripping
real validation wherever the CLI happened to be the stricter side.

**Generate payloads mechanically from canonical models.** Attractive and not chosen
now: it presumes every canonical model is already correctly constrained, which the
`B_CLI_ADDS` findings disprove. Generation would faithfully reproduce a
`DataInventoryCasilla` that validates nothing. Revisit once the invariant migration
below is complete.

## Decision

A CLI payload is a PROJECTION of a canonical model. It may loosen a type for the wire.
It may not declare a constraint of its own, and it may not restate one.

The codebase already contains the sanctioned shapes; this decision names them rather
than inventing a mechanism. A census of how ESTABLISHED each shape is was run before
this ruling, because naming a one-off as precedent would be the same error this ADR
exists to correct.

1. **Shared validator** -- ESTABLISHED, 12 call sites across four CLI payload modules
   and four distinct shared functions (`validate_modelo_work_deadline_posture`,
   `validate_utc_aware`, `validate_inclusive_iso_date_range`, and the invoice identity
   validators). One rule, one implementation, two callers. This is the default shape.
2. **Reconstruction** -- ESTABLISHED BUT THIN, four occurrences across four modules,
   each framing itself in its own docstring as deliberate reuse ("Rebuild the canonical
   selection so flattened fields cannot drift"). The payload's validator rebuilds the
   canonical model, rerunning its validators, so the backend stays the authority. Use
   where a payload flattens several canonical fields and the invariant spans them.
3. **Kwargs carrier** -- PERMITTED, NOT PRECEDENT. Structurally the strongest of the
   three, because no parallel model exists at all: a `TypedDict` whose only role is to
   build arguments for the real constructor. But the census found exactly ONE instance
   (`_ImpersonationKwargs` for `GoogleImpersonationConfig`) out of eight TypedDicts
   under `entrypoints/cli/`, the other seven being text-rendering row shapes. It is
   sanctioned where a command builds a canonical object rather than reporting one; it
   is not evidence of a convention and must not be cited as though it were.

The forbidden fourth shape is an independently-declared payload that restates or
invents constraints.

Each divergence direction therefore gets the OPPOSITE fix:

- A constraint the CLI ADDS is migrated INTO the canonical model, then deleted from the
  payload. The rule was real; it was in the wrong layer.
- A constraint the CLI DROPS is restored by projecting rather than restating, under one
  of the three shapes above.

## Implementation

Sequencing follows severity, not count. The `B_CLI_ADDS` set is corrected first,
because until an invented rule reaches the backend the canonical model is knowingly
under-constrained and any later generation step would bake that in. The `A_CLI_DROPS`
set follows, invariant-bearing cases before bound-bearing ones. The ~67 equivalent
pairs are converted last and are the cheapest.

This is model reconciliation, not mechanical rehoming: deciding whether an invented
constraint is a genuine domain rule or a presentational nicety is a judgement about the
domain, and a wrong call either strips validation or writes CLI opinion into the
backend. It is assigned accordingly.

The replacement invariant is mechanical rather than reviewed: a gate that reds when a
CLI payload declares a `Field` constraint, `field_validator` or `model_validator` that
its canonical counterpart does not. That makes "the CLI invented a rule" detectable
instead of a matter of reviewer attention, and it must be mutation-proved by adding
such a constraint and confirming the gate fires.

## Consequences

Every rule the backend enforces becomes reachable by every consumer of the backend, not
only by the CLI that happened to declare it. The ~11 invented constraints strengthen
the canonical models permanently.

The cost is that ~46 pairs need individual judgement before any of them can be
projected. The two previously unread pairs are now classified: `ApoderadoStatus` is a
twelfth `B_CLI_ADDS` (the CLI bounds `represented_nif` and `catalogue_version` where the
canonical declares them unbounded), and `ApoderadoConfiguration` is equivalent.

The risk this decision accepts is that migrating an invented constraint into a canonical
model can break a producer that was legitimately emitting values the CLI never saw. Each
migration is therefore a behaviour change to be tested against real producers, not a
declaration move.
