---
tags:
  - '#adr'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-17'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-research]]"
  - "[[2026-07-05-cpdefix-followup-allgreen-audit]]"
  - "[[2026-07-05-cpdefix-followup-allgreen-adr]]"
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---

# `cpdefix-followup-allgreen` adr: `campaign disposition tracker` | (**status:** `accepted`)

## Problem Statement

The cpdefix follow-up campaign is open ended: new persona evidence can appear while other agents are concurrently changing the calculation tree. The previous closeout material contains useful findings, but several blocker labels are now stale at current HEAD. Without a current campaign disposition, workers can waste time re-fixing landed M720 work, over-promote the M347 counterpart provider, or claim allgreen without fresh gates.

This ADR records the campaign governance decision behind the L3 tracker. It is a process and orchestration decision, not a product source-kind design. It does not supersede the accepted counterpart-source provider ADR, the Modelo 720 row-carrier plan, or any registry family authority.

## Considerations

- The user explicitly requested an orchestrated, wave-based vaultspec plan, continuous refinement as evidence changes, subagent delegation for code work, and closure of completed agents.
- Every code fixer must ground with `vaultspec-rag` before editing, then confirm with grep. This binds discovery, briefs, and review.
- The shared worktree is busy. Workers must not revert or overwrite unrelated WIP, and must avoid destructive git commands.
- Current evidence shows M720 row carrier and `foreign_asset` enrollment have landed. Reopening that blocker without a fresh failure would create churn.
- Current M347 support is invoice-owned. The reserved counterpart provider remains gated by the accepted counterpart-provider ADR until a ledger or purchase-evidence binding trigger co-lands with provider enrollment.
- The June cpdefix audit was a scoped calculation checkpoint, not full-tree or vault-wide allgreen certification.

## Considered options

- **Option A: continue from old closeout blockers as if current.** Rejected because current M720 and M347 evidence has changed; this would dispatch stale code work.
- **Option B: skip vault planning and track only in chat.** Rejected because the campaign is open ended, multi-agent, and needs a durable schedule plus exec evidence.
- **Option C: treat every stale blocker as closed and claim allgreen now.** Rejected because full-tree, vault-wide, and persona-artifact completeness remain unclaimed surfaces.
- **Option D: maintain an L3 wave tracker that revalidates evidence before dispatch.** Accepted because it preserves momentum while preventing stale code churn and overclaiming.

## Constraints

- The tracker must not authorize any source-kind promotion by itself. Source-kind and provider changes remain governed by their own ADRs and registry gates.
- The counterpart provider cannot be enrolled until its accepted ADR trigger fires.
- No fallback code path, shim, or reexport may be introduced merely to pass a campaign gate.
- Plan rows require evidence. Checked rows need execution records or an audit explicitly recording a formal deferral.
- Stale findings are retired by audit evidence and focused gates, not by assumption.

## Implementation

Use a tier-L3 vault plan with three waves:

- Current truth refresh: re-read persona and vault evidence, separate stale blockers from live defects, and keep agent briefs grounded.
- Calculation edge hardening: work only edges that remain live after the refresh, with M347 source ownership and deferred source partitions first.
- Verification and closure: run focused gates before broad calculation gates, then close rows with execution records and vault checks.

The orchestrator owns briefing, supervision, verification, and plan updates. Code fixers own bounded source edits only after a RAG-grounded brief identifies a current defect and write scope.

## Rationale

The research shows the same evidence can change category as the codebase progresses: M720 moved from blocker to landed row-carrier/enrollment work, and M347 moved from no relevant bindings to invoice-owned summary support while the reserved provider stayed gated. A tracker that starts with truth refresh is therefore safer than direct coding, and more honest than declaring allgreen from historical green gates.

## Consequences

- The campaign has a durable schedule that can absorb new testimonials without assuming the testimonial set is bounded.
- Stale blockers are still recorded, but they no longer drive code work unless current tests reproduce them.
- The counterpart provider remains protected from premature enrollment.
- The plan adds process overhead: research, ADR, audit, plan, and exec records are required even for orchestration work. That overhead is accepted because it keeps the multi-agent campaign auditable.
