---
tags:
  - '#adr'
  - '#plan-triage-approach'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-executable-parity-evidence-tier-contract-adr]]"
  - "[[2026-06-02-m390-annual-autoconsumo-promotor-source-adr]]"
  - '[[2026-06-04-plan-triage-approach-research]]'
---


# `plan-triage-approach` adr: phased triage by feature-state-honesty + bulk-archive for landed-feature plans | (**status:** `accepted`)

## Authoring note

Authored via Write tool — same bash constraint as the prior ADRs this campaign. Commit-bot validates via `vault check all`.

## Problem statement

838 open plan Steps across 20 vault plans accumulated as a backlog. Four parent triage tasks (#143-#147) have been in_progress since session start with zero net progress because the dispatch shape was ambiguous: how do you process 838 Steps without either (a) bulk-closing things that aren't actually done, or (b) drowning agents in per-Step audits for work that's clearly landed?

The `aeat-agent-delivery` rule states: "Keep project board In Progress limited to actively worked items with a worktree and delegation. Do not mark charters, placeholders, or intent as active execution." 838 open Steps violates this rule's spirit — most cannot be "actively worked" simultaneously. The triage's purpose is restoring board honesty.

Three candidate shapes per PM:
- **(a) Bulk plan-archive**: close out plans whose features are landed.
- **(b) Step-level audit**: catalogue each Step's status individually.
- **(c) Phased triage by feature priority**.

## Forces in tension

- **Honesty discipline**: per `aeat-agent-delivery`, the board must reflect reality. Open Steps for landed features mislead future agents about what's outstanding.
- **Cost vs accuracy**: full Step-level audit (b) at 838 Steps is ~40 hours of agent time at 2-3 minutes per Step. Bulk archive (a) saves time but risks closing genuinely-open Steps.
- **Cross-plan dependencies**: some Steps in one plan reference work in another. A bulk-archive approach must account for cross-references or risks orphaning citations.
- **Feature-level coherence**: plans whose features are wholly landed (M210 Phase 1, source_jurisdiction axis, implies_nonzero operator) have predictable Step states. Plans whose features are partially-landed (M303 hardening, suite-redgreen) need finer triage.
- **Lesson #1 from this campaign (M131 S398 rollback)**: don't close work without grounding. A bulk archive that closes a Step whose claimed deliverable isn't actually in the diff is the same anti-pattern that produced the false-implication regression. The triage MUST verify before closing.

## Decision: hybrid phased approach — bulk-archive landed-feature plans, Step-level audit for in-flight plans, defer never-started plans

The right shape combines (a) and (b) along a feature-state axis. Three buckets, three procedures:

### Bucket 1 — Landed-feature plans → bulk-archive

A plan is "landed-feature" when:
- Every Phase has a verifiable closure commit (ADR, exec record, or feature-shipping commit cluster).
- No Step references a still-open dependency in another plan.
- The feature's persona-replay tests pass (where applicable).

For these plans, the triage agent runs ONE verification pass per plan (not per Step):
- `git log --grep='<feature-tag>'` produces the commit cluster.
- `vault feature index <feature-tag>` produces the document trail.
- A single audit doc per plan captures the landed-feature claim with cross-citations.
- The plan archives via `vault plan archive` (or `vault feature archive`) with the audit doc as the rationale.

Estimated: ~5-7 of the 20 plans qualify (source_jurisdiction axis, implies_nonzero operator, m210-irnr-full-engine Phase 1 if landed, the typed-constant migrations, etc.). ~5 hours total. Saves the ~15-20 hours that Step-level audit would consume.

### Bucket 2 — In-flight feature plans → Step-level audit

A plan is "in-flight" when:
- Some Phases have closure, others don't.
- Steps reference open dependencies in other plans.
- Feature is partially-shipped (e.g. M303 hardening, suite-redgreen burndown).

For these plans, the triage agent runs per-Step verification:
- Per Step: `git log --grep='<step-id>'` + `git show <sha>` against the cited path to verify deliverable matches the Step's scope.
- Classify per the existing taxonomy: DONE (with verified commit-sha), DONE-NO-CITE (with justification line), OPEN (with sizing + blockers), STALE-SUPERSEDED (with superseding-Step or retiring-ADR citation).
- Per-plan audit doc captures the classification table.

Estimated: ~8-10 of the 20 plans qualify. ~25-30 hours total. Higher cost justified by uncertainty.

### Bucket 3 — Never-started / charter plans → defer

A plan is "never-started" when:
- Zero Phases have closure.
- The plan exists as forward-design intent (charter, scoping doc).
- No Steps have been worked.

For these plans, the triage agent does NOTHING beyond a one-line per-plan note: "deferred; charter only; no Steps worked." The plan stays as-is; the parent task closes with the deferral note.

Estimated: ~3-5 of the 20 plans qualify. ~30 minutes total.

### Sequencing

1. Architect (or PM) classifies each of the 20 plans into one of three buckets via a 30-minute scan. Output: a routing table.
2. Bucket 1 plans dispatch first (highest ratio of board-honesty restoration to agent-time).
3. Bucket 2 plans dispatch second, with the per-Step audit procedure.
4. Bucket 3 plans get the deferral note last, with no agent dispatch.

The grounding-before-closure discipline (lesson #1) applies at every Step closure in Bucket 2: `git show` MUST verify the cited commit contains the claimed deliverable. Bulk closures in Bucket 1 require ADR / exec-record / feature-replay grounding, not just commit-message word.

## Why not (a) alone

Bulk-archive without Step-level audit for in-flight plans risks closing genuinely-open work. The M131 S398 rollback proved that even well-intentioned grounding can miss real defects; relying on plan-level grounding alone for in-flight plans loses the per-Step granularity. Reject pure (a).

## Why not (b) alone

Step-level audit at 838 Steps is ~40 hours. Most of that effort is wasted on Bucket 1 plans where the feature has demonstrably landed and the per-Step audit produces no new information. Reject pure (b).

## Why not (c) — phased by feature priority

PM's framing of (c) as "phased triage by feature priority" implies the priority axis is feature-importance. The actual cost-saving axis is feature-state (landed / in-flight / never-started), not feature-priority. A high-priority landed feature still warrants only bulk archive; a low-priority in-flight feature still warrants Step-level audit. Feature priority is the wrong discriminator. The phased-by-feature-state framing in this ADR is closer to PM's (c) but with the correct axis.

## Consequences

- 20 plans classified into 3 buckets via 30-min scan.
- ~5-7 plans archive after ~5 hours of Bucket-1 dispatch.
- ~8-10 plans get per-Step audit via ~25-30 hours of Bucket-2 dispatch.
- ~3-5 plans get deferral notes via ~30 minutes.
- Board honesty restored: open Steps reflect actually-outstanding work.
- Future plan-triage rounds reuse the bucket classification as the dispatch template.

### Anti-tautology gate

For each archived Bucket-1 plan, a structural-test ratchet asserts (a) the plan's feature-tag has at least one closure commit cluster, AND (b) no other open plan's Steps cite this plan's Steps as a dependency. If either fails, the archive is rejected. Prevents archiving a "landed-feature" plan that other in-flight plans still depend on.

### Dispatch shape

This ADR adjudicates the triage approach; the bucket-classification scan + per-bucket dispatch happens in follow-up tasks:

- New task: "Classify 20 plans into Bucket 1/2/3 per ADR" — 30 min architect or PM work.
- New tasks per Bucket-1 plan: "Archive plan X with audit doc" — coder dispatch, ~30-45 min each.
- New tasks per Bucket-2 plan: "Step-level audit of plan Y" — discovery dispatch, ~2-4 hours each.
- One task closing Bucket 3 with deferral notes.

The four currently-in_progress parent tasks (#143-#147) close once the bucket-classification scan lands; their work decomposes into the new task list above.

## Out of scope

- Authoring new plans for future work. The triage is backward-looking.
- Reorganising the plan-tier taxonomy (L1/L2/L3/L4). Tier structure is documented in the plan-hardening convention ADR; this ADR doesn't touch it.
- Inventory ratchet sweeps (#159 family) — separate deferred-with-documented-rationale concern.
