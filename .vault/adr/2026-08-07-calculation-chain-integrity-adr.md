---
tags:
  - '#adr'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:ccce394582de9674b9a6e644db325fdb50923558e0463af49d65bb28f573353b'
related:
  - '[[2026-08-07-silent-zero-regression-screen-adr]]'
  - '[[2026-06-19-silent-zero-base-aggregation-adr]]'
  - '[[2026-08-06-llm-invoice-read-reconciliation-adr]]'
  - '[[2026-08-05-ledger-invoice-decomposition-adr]]'
  - '[[2026-08-07-calculation-chain-integrity-m390-annual-under-modelling-research]]'
---
# `calculation-chain-integrity` adr: `Roll-up sequencing and scope for the silent-zero/silent-overclaim remediation waves` | (**status:** `accepted`)

## Problem Statement

`2026-08-07-calculation-chain-integrity-plan` is a roll-up plan (five waves) executing decisions that belong to no single component's ADR: sequencing across waves, scope boundaries on how far a wave reaches, and standing-versus-blocking classification of cross-cutting work. Several of these rulings were made in conversation during execution and exist nowhere else, which is the exact failure this session found twice already -- a decision that lives only in chat is a decision a later reader cannot find. This record captures the roll-up's own sequencing and scope rulings. It does NOT decide the component questions those waves execute: `silent-zero-regression-screen`, `ledger-invoice-decomposition`, and `llm-invoice-read-reconciliation` each own their own decision and are cited, not restated, here.

## Considerations

- The vaultspec exec-scaffold lifecycle gate checks for an ADR's EXISTENCE under a plan's feature tag, not the meaningfulness of its content; a roll-up plan whose governing ADRs sit under other feature tags has none of its own until one is authored here. This record exists partly to satisfy that structural need, but only because it also has genuine sequencing/scope content to record -- an empty placeholder would not earn its place.
- `.vault/reference/2026-05-15-linkage-design-audit-reference.md` finding T-05 already establishes the accepted pattern for "declare where a routed value lands": a domain-owned Python constant mapping plus a `CrossDomainSnapshotCheck` validated at snapshot-build time, NOT a new registry TOML schema field. This is prior art for `W01`, reached the same way `2026-05-26-modelo-130-relation-regression-adr` was reached for `W02` -- by reading the established pattern before designing a new one.
- `2026-08-07-silent-zero-regression-screen-adr` (accepted) explicitly frames `W02.P03` as a campaign, not a commit: a per-family reachability probe pattern replicated across 7+ source kinds before the pattern itself is validated is seven things to unpick if the shape is wrong.
- The canonicalisation sweep (three rate-to-IVA-category tables reducing to one) is operator-directed standing work, independent of any other wave's completion.

## Considered options

Each item below is a scope/sequencing choice, not a technical design choice -- the technical alternatives were weighed in the component ADR each defers to.

1. **`W01`: registry schema field vs. established T-05 pattern.** A new `output_casilla_id` field on the binding schema was the plan's original text. Rejected in favour of the T-05 pattern (Python constant + cross-domain snapshot check) because a schema field reopens a settled cross-domain routing design with no ADR proposing to reopen it, while the constant-plus-check shape is already accepted, already shipped for the Renta first-slice case, and closes the identical hazard (a routed value with no validated destination).
2. **`W02.P03`: all source families at once vs. one family first.** All-at-once was rejected: the per-family reachability-probe SHAPE is unproven until one family's probe, mutation proof, and residual-limit docstring exist end to end. One family first, then a mandatory stop-and-report, converts an unproven pattern replicated seven times into one validated design plus six informed repeats.
3. **Retención-chain wiring order.** Wiring the ledger-backed retención binding to its casilla before the destination casilla's own scaling/aggregation is coherent was considered and rejected: wiring first would route the value onto the wrong (income) casilla before the destination is ready to receive it correctly. The ruling is: make the destination casilla's own aggregation coherent, declare the destination (via the `W01` T-05 pattern), THEN wire the retención binding to it.
4. **Canonicalisation sweep: precondition vs. standing work.** Gating the other waves on the three-rate-table canonicalisation landing first was considered and rejected -- it is operator-directed standing work with its own cadence, not a dependency any other wave's completion requires.

## Constraints

- This record decides sequencing and scope only. A reader looking for the technical shape of the detection mechanism, the invoice decomposition, or the LLM read-reconciliation classifier must follow the citation to that component's own ADR; restating that content here would fork it.
- No wave in this plan proceeds past its authorised scope without its own gate: `W02.P03` stops after one family; the canonicalisation sweep runs on its own schedule; `W04`'s decision-blocked dispositions do not move until their named operator ruling lands.

## Implementation

Four rulings, each binding one wave or cross-wave concern:

**`W01` (registry structural truth).** Declare the renta-income binding family's output destination via the T-05 pattern -- a domain-owned Python constant mapping plus a `CrossDomainSnapshotCheck` registered at snapshot-build time -- not a new registry schema field. Retire the hardcoded backend-inputs override once the constant-plus-check pair is live, in that order: coherent destination aggregation, then declared destination, then the retención binding wired to it. Wiring before the destination is ready routes the value onto the income casilla instead.

**`W02.P03` (detection gate construction).** One binding-source family only, chosen for the simplest declared selector shape. Full loop required before touching a second family: the reachability probe, the mutation proof (a binding retargeted to match nothing must redden the gate, revert, confirm green), and a docstring stating what the probe cannot catch. Stop and report after the first family; do not proceed to a second without that report being read.

**`W03`/`W04` (activity-type axis; decision-blocked dispositions).** Unchanged from the plan's own text -- no roll-up-level sequencing ruling was needed beyond what those waves' own Steps already state.

**Canonicalisation sweep.** Proceeds on its own cadence as operator-directed standing work. Not gated behind, and does not gate, any wave in this plan.

## Rationale

Each ruling resolves a scope or sequencing ambiguity the plan's own Step text left implicit, and each resolution came from reading an existing accepted decision rather than inventing a new one: `W01`'s ruling from `T-05`'s already-shipped pattern, `W02.P03`'s ruling from the campaign-shaped consequences already named in `2026-08-07-silent-zero-regression-screen-adr`, the retención-chain ordering from the mechanical fact that a destination must be ready before a value is routed to it. None of these needed a new technical decision; they needed the roll-up's own record to state, in one place, what a reader executing later Steps would otherwise have to reconstruct from chat history.

## Consequences

Gain: the plan's cross-wave sequencing survives this session rather than living only in the conversation that produced it -- the same protection `S05`/`S06` gave the detection-mechanism decision, applied to the roll-up itself. The exec-scaffold lifecycle gate is also satisfied for every remaining Step in this plan, as a consequence of this record actually deciding something rather than as its purpose.

Honest difficulty: an umbrella record for a roll-up plan is a genuine hazard if it drifts into re-deciding what the component ADRs already settled -- the boundary stated in Constraints (sequencing and scope only) is what prevents that, and it must be checked again at each future ruling recorded here, not assumed to hold automatically because it was stated once.
