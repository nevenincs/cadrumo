---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:fc0678fb3be3d0bd891ed1ea11887a08eb144dae1fe7b4db8b5a94c9eb19ed75'
step_id: 'S40'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# confirm every step in this plan is checked with an exec record or formally deferred with a follow-up reference, and only then declare the campaign structurally complete

## Scope

- `.vault/plan/2026-08-10-casilla-schema-plan.md`

## Description

- Enumerate every Step in the plan through the owning status verb and confirm each is checked.
- Confirm each checked Step resolves to a matching execution record, with no Step reported as having no record.
- Confirm P11, the open-ended intake phase, holds no open Steps, since the plan's own completion criterion requires it to be empty rather than declared done.
- Confirm the P12 gates hold: the honesty review persisted with every finding actioned or deferred, and the campaign rule retired with its provider copies swept.
- Re-run the feature-scoped vault check and require it clean.

## Outcome

The initial close observation found every Step checked with a matching execution record and a clean feature-scoped VaultSpec check. It also recorded that the final commits had not landed because the shared Git index was locked.

The subsequent delivery audit rejected that working-copy-only state as completion. S87, S88, S90, S91, S92, S36, S39 and S40 were reopened through the owning plan CLI because their implementation, review or lifecycle artefacts remain modified or untracked rather than reachable from `HEAD`. The current status is therefore 44 closed and 8 open, with S87 next. This receipt is a record of the rejected close attempt, not evidence that the campaign is currently complete.

Current feature evidence remains substantive: the S88, S91 and S92 focused lanes pass 15, 22 and 2 tests respectively; registry verification passes; locale scaffold parity passes; and the feature-scoped VaultSpec check passes all dimensions. Repository-wide completion does not: five of six fast static gates are red on concurrent shared-tree work, global VaultSpec exits non-zero on a peer-owned plan schema error, and normal Git commit is blocked by the frozen `.git/index.lock`.

**Third close observation, 2026-08-13 - ACCEPTED.** The condition this record set for reopening is discharged, and the campaign is declared structurally complete.

The reopening was correct and its bar was the right one: artefacts had to be *reachable from `HEAD`*, not merely present in a working copy. That bar is now met, and it was verified per Step rather than in aggregate - S83 at `ed05a92be1`, S88 at `e03e201d9f` and `3241d5a173`, S90 by identical `HEAD`-versus-worktree Modelo 303 label counts with no casilla-label keys in the dirty locale diff, S91 and S92 at `e03e201d9f`, S87 and the S36 honesty review at `bced74f746`, S39 at `f06e68dd3c`. None of those paths is dirty in the working tree. The `.git/index.lock` holder that blocked the second attempt is gone; it was never deleted, moved, truncated or renamed by any agent.

Enumeration through the owning status verb: 52 of 52 Steps checked, `exec-mapping` clean, so every closed Step resolves to a matching execution record. P11 holds no open Steps, which is the plan's own criterion for that phase - empty rather than declared done. The feature-scoped `vault check all` passes all nineteen dimensions. The S87 index was regenerated through its owning verb and returned an identical document list.

**Completion measured against the four ADRs' decision statements, not a paraphrase.** All four surfaces were re-verified at `HEAD` this session: the four facade-exported registry derivations including the amended ledger-IVA invariant gate carrying its own non-vacuity assertion; `OperatorActionAxis` with its total import-asserted projections and exactly one surviving discrepancy enum; `ModeloWorkReview` with the three origin layers side by side, the two-member anomaly enum, one `BlockerRef` shape at both grains, and a ratio-token gate that walks the whole JSON schema recursively and bars `float`; and all four dead-surface dispositions, with `verify_export` wired as the post-write self-check and zero references to the three deleted symbols.

**Carry-forward, triaged and peer-owned.** The registry suite is red at `HEAD` - 157 deterministic failures across nine root causes, diagnosed in `2026-08-13-registry-suite-red-at-head-audit` and carried by `2026-08-13-registry-suite-red-at-head-plan`. Owner triage places none of it on a casilla-schema surface: the causes are the M100 maternidad binding harness sweep, the IVA deduction-authority fixture sweep, the `_IvaLedgerSelector` required-field sweep, four registry-data gaps, and the critical finding that CI has not completed a unit-lane run since 2026-08-07. The plan's own global gate is serial full-tree *collection*, which is clean at 32,665 tests. This campaign closes on owner-surface green with the tree-wide red referenced rather than absorbed, per the owner ruling of 2026-08-13.

That distinction is the honest one and should not be read as broader than it is: **campaign complete is not tree healthy.** The same audit records that the AEAT-grounded oracles for M322, M353 and M390 do not currently execute, so the engine's grouped-entity and annual-summary IVA figures are unverified rather than proven correct. Nothing in this campaign's scope caused that and nothing in its scope fixes it.

## Notes

No alternate index, `commit-tree`, or other plumbing workaround is authorised or used. The lock is not deleted, moved, truncated or renamed. The reopened Steps stay open until their exact path groups can land through the normal shared index, the final index can be regenerated after those landings, and S36/S39/S40 can be re-reviewed against reachable commits and current repository-wide gates.

No plan checkbox is treated as a substitute for a commit. No data loss and no destructive Git operation occurred.

No checkbox in this plan was treated as a substitute for a commit, in this attempt either.

**The review screen's transitional placement, recorded at close 2026-08-13.** This campaign's W04.P10 delivered the review screen into `src/cadrumo/adapters/inbound/tui/`, which is not where a Textual surface belongs - `2026-08-11-tui-architecture-adr` D10 designates `src/cadrumo/entrypoints/tui/` as the sole production TUI root and D12 requires the legacy inbound package deleted without a compatibility facade. Nothing is excluded from that standing goal, and the placement is transitional, not permanent.

The structural defect was that no row owned the exit: the tui-architecture plan demanded, in its Verification section, that no Textual code live outside `entrypoints/tui`, while no Step in it named this screen. That is how a plan and a tree drift apart with both looking green. `W04.P10.S104` is now inserted in that plan to relocate the screen and its tests to `cadrumo.entrypoints.tui.modelo.view` as a read-only consumer of the public `application.modelo` facade and delete the legacy screen, exports and locale references in the same change. The obligation is carried by a plan row instead of by audit prose.

This does not reopen any Step here. The screen was delivered and closed in its sanctioned transitional scope under S34 and S35, and the closure evidence in the Outcome above is unaffected. A correction is noted for the next reader: an earlier version of this note, committed the same day, recorded the placement as permanent and the topology consolidation as excluded from the standing goal, on a mistaken reading that the TUI campaign had been cancelled. It had not been.

This does not reopen any Step of this campaign. The screen was delivered and closed in its sanctioned transitional scope under S34 and S35; what changed is only that the obligation to move it is now carried by a plan row in the owning campaign instead of by prose in an audit. The closure evidence in the Outcome above is unaffected.
