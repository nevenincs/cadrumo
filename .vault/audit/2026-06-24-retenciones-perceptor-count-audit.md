---
tags:
  - '#audit'
  - '#retenciones-perceptor-count'
date: '2026-06-24'
modified: '2026-06-24'
related:
  - '[[2026-06-24-retenciones-perceptor-count-adr]]'
  - '[[2026-06-24-retenciones-perceptor-count-plan]]'
---

# `retenciones-perceptor-count` audit: `Shared-worktree WIP-discard incident + RET-1 P02 live-contention; uncommitted is not orphaned`

## Scope

Records (1) a destructive-git incident during RET-1 (#6) P02 — the coordinator discarded an
uncommitted peer change believing it orphaned, and it was live — and (2) the resulting
shared-worktree coordination lesson, alongside the reconciliation-campaign status as of 2026-06-24.
The `aeat-git-worktree-safety` rule mandates that a destructive-git event be logged; this is that
record, written by the coordinator about its own action.

## Findings

### INCIDENT-1 (HIGH) — discarded a LIVE peer's working-tree WIP on a false "orphaned" premise

A casilla-id-canonicalization change (adds `validate_casilla_input_ids`, threads it through
`calculate_modelo_revision`) sat uncommitted in `src/aeat/application/modelo/_calculation_actions.py`
for many turns. It blocked RET-1 P02's mesh enrollment (which must edit that file) and caused
locale-scaffold drift. Grounding suggested orphaned: `git grep HEAD` found zero committed consumers
of the symbol (uncommitted-only), and both *reachable* teammates disclaimed it. On that basis the
user authorised discarding it; the coordinator saved a recovery patch
(`.agents/discarded-wip/`), discarded ONLY that file (surgical: 432→431 dirty), verified clean.

Within minutes the WIP **re-appeared** — a third, unaddressable agent re-applied it. The "orphaned"
premise was false: an uncommitted change with no *reachable* owner is not safely orphaned; a live
agent the coordinator cannot message can own it, and **re-appearance after a discard is proof of
life**. The discard had destroyed live in-progress work (recovered by the owner re-applying + the
saved patch). The owning agent then re-applied repeatedly, creating a live race on the file.

### INCIDENT-2 (HIGH, AVERTED) — refusal to escalate the destruction via a different mechanism

With the file racing, the executor proposed reconstructing it from `HEAD` via a file `Write` (wiping
both the live WIP and re-applying only its own enrollment) to force a clean atomic commit. The
coordinator REFUSED: the mechanism (file `Write` vs `git restore`) is irrelevant — both destroy a
live peer's actively-maintained work and restart the race. A prior authorization to discard an
*orphaned* WIP does not extend to overwriting a *proven-live* peer's work, and a teammate proposing
the mechanism cannot supply that authorization. No re-discard, no reconstruct was performed.

### STATUS (informational) — campaign converged except one live-contended enrollment

13 of the 16 original cross-period/aggregation findings plus the enum gate (#17) are landed +
pushed. RET-1 (#6) P01 (the dedicated encrypted distinct-NIF per-perceptor store) landed at
`2b46d156d`; P02 (resolver + `RETENCIONES_AGGREGATION` source kind + per-family bindings module +
empty-store no-silent advisory) is BUILT and green across its 9 own files (548 passing), held
uncommitted only because its 2-line mesh enrollment must land in the live-contended
`_calculation_actions.py`. #2/#3 (M303 REDEME field + last-period refund election) are in the ADR
phase. The recurring shape across the campaign: multiple campaigns contend the same mesh/registry
files; the clean resolution is always commit-then-handoff (the `_relation_prefill.py` handoff
worked), never a concurrent overwrite.

## Recommendations

- Resolve INCIDENT-1's residue by COORDINATION, not force: the operator identifies the
  casilla-id agent and either directs it to COMMIT its `_calculation_actions.py` WIP (then the
  executor re-applies the captured enrollment patch on the clean-committed file and commits P02
  atomically) or pauses it for a clean window. The coordinator will not re-discard or overwrite.
- Treat any uncommitted change whose owner is not reachable as LIVE-CONTENDED, not orphaned, unless
  the operator confirms abandonment AND it does not re-appear after a clean. Always save a recovery
  patch before any authorised discard.
- Register every dispatched agent in the shared task list / messaging roster so no agent's WIP is
  unaddressable; an unaddressable live agent is the root cause of this incident.

## Codification candidates

- **Source:** INCIDENT-1 + INCIDENT-2.
  **Rule slug:** `uncommitted-wip-is-not-orphaned`.
  **Rule:** An uncommitted working-tree change with no *reachable* owner MUST be treated as
  live-contended, never silently orphaned: never discard or overwrite it (by `git restore`/`checkout`
  OR by file `Write`-from-HEAD — the mechanism is irrelevant) without operator-confirmed abandonment,
  always save a recovery patch first, and treat re-appearance after a clean as proof the owner is
  live (stop; coordinate a commit-then-handoff, do not re-clean). Hold promotion until this has held
  across one more cycle (per the codify discipline — this is its first encounter).
- **Deferred (from sibling ADRs, pending their features landing + holding a cycle):**
  `retenciones-counts-are-distinct-not-summed` (RET-1 ADR), `cross-period-carry-balances-are-reconciled`
  (M200-BIN-continuity ADR), `annual-return-aggregates-its-headline-figure` (EOY ADR).
