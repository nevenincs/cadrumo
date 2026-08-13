---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:ea00b07a9fba3e9bfb6348bc32e32e22aa2e2b26ef714e715f6c3b3510ee12ff'
step_id: 'S36'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

# run the fresh-context honesty review of the campaign close and record it as a vault audit with every finding actioned or deferred

## Scope

- `.vault/audit/`

## Description

- Re-run the campaign-close honesty review as a review-as-if-inherited pass, one of the three sanctioned forms, and state the form in the audit rather than leaving a reader to infer it.
- Quote the decision statements of the four governing accepted ADRs verbatim and measure completion against them, never against a paraphrase or a narrowed reading.
- Reconcile every one of the first review's seven findings against current HEAD and record its disposition.
- Re-run the campaign's own gates and the plan's global collection gate, and record the figures.
- Record every finding this pass discovered, each actioned or formally deferred with a reference.

## Outcome

The re-review is persisted as `2026-08-12-casilla-schema-s36-campaign-close-re-review-audit` with verdict **PASS**.

All seven findings of the first review are resolved with verification. Four further findings surfaced by this pass - the Modelo 303 deducible-fold regression, the mandatory-Spanish casilla-label coverage gap, two attribution defects in the retired-revision cutover gate, and two registry-diff anchors invalidated by the span split - were actioned in-session under S88, S90, S91 and S92. None was deferred.

Verification recorded in the audit: 32,665 tests collected serially across `src`, `dev` and `packaging` with an empty marker override, exit zero; 47 passed across the eight affected modules; registry authority validation clean; zero unresolved Modelo 303 casilla labels across all six revisions and all four catalogues, measured through the production resolver; `dev.locales scaffold --check` `ok` for all four; feature-scoped vault check clean on every dimension; every closed Step carrying a matching execution record; P11 holding no open steps.

One carry-forward, environmental rather than substantive: the campaign's final commits have not landed, because `.git/index.lock` has been held by a dead process since 19:31:00.

## Notes

The first review's `iva-stem-gate-prose` finding named two lines. The gate reported three: the paragraph reporting the finding reproduced the prohibited token itself. Correcting only the two named lines would have left the gate red and the campaign closing over it, which is the exact failure a close review exists to catch - and the review that found it was itself the source of the third occurrence.

A peer's uncommitted previous-filing coverage validator transiently reddened whole-tree registry validation on Modelo 130 and Modelo 720 during this pass. The peer reverted it and validation recovered; every figure was re-measured afterwards, and the episode is recorded in the audit so a reader comparing timestamps does not see two contradictory verdicts without an explanation.

This record and the audit were authored through the VaultSpec owning verbs. No plan structure was changed by the review itself. No data loss and no destructive Git operation occurred.

**Carry-forward discharged 2026-08-13.** The single environmental carry-forward this review recorded - the campaign's final commits not having landed behind a dead `.git/index.lock` holder - is resolved. The lock is absent and every artefact this review measured in the working tree is now reachable from `HEAD`, verified per Step rather than in aggregate: S83 at `ed05a92be1`, S88 at `e03e201d9f` and `3241d5a173`, S90 by identical `HEAD`-versus-worktree label counts, S91 and S92 at `e03e201d9f`, S87 and this audit at `bced74f746`, S39 at `f06e68dd3c`. The review's PASS verdict therefore stands on reachable commits, which is the condition it made its own completeness claim conditional on.

No finding of this review was reopened by the discharge, and no expectation was moved to reach it.
