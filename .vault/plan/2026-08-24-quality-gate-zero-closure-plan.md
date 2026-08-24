---
tags:
  - '#plan'
  - '#quality-gate-zero-closure'
date: '2026-08-24'
tier: L3
related:
  - '[[2026-08-24-quality-gate-zero-closure-adr]]'
  - '[[2026-08-24-quality-gate-zero-closure-static-gate-matrix-research]]'
  - '[[2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference]]'
  - '[[2026-07-14-honest-all-green-adr]]'
  - '[[2026-06-09-quality-hardening-campaign-adr]]'
  - '[[2026-06-04-repo-health-triage-adr]]'
modified: '2026-08-24'
body_hash: 'sha256:db82aa658fe4b2b2082e2743d20e826f0e60be5f24992d484fdc61586ac34185'
---
<!-- RETIRED: W01, W02, W03, W04, W05, W06, P01, P02, P03, P04, P05, P06, P07, P08, P09, P10, P11, P12, P13, P14, P15, P16, P17, P18, P19, S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S12, S13, S14, S15, S16, S17, S18, S19, S20, S21, S22, S23, S24, S25, S26, S27, S28, S29, S30, S31, S32, S33, S34, S35, S36, S37, S38, S39, S40, S41, S42, S43, S44, S45, S46, S47, S48, S49, S50, S51, S52, S53, S54, S55, S56, S57, S58, S59, S60, S61, S62, S63, S64, S65, S66, S67, S68, S69, S70, S71, S72, S73, S74, S75, S76, S77, S78, S79, S80, S81, S82, S83, S84, S85, S86, S87, S88, S89, S90, S91, S92 -->

# `quality-gate-zero-closure` plan

## Description

This L3 roll-up activates the accepted 2026-08-24-quality-gate-zero-closure-adr, grounded by 2026-08-24-quality-gate-zero-closure-static-gate-matrix-research and 2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference, alongside the standing decisions in related frontmatter. It does not close the evolving codebase or freeze a snapshot of current findings. It activates a durable rolling controller that observes the current HEAD, claims disjoint work, repairs owner-approved batches, rechecks affected and global gates, and publishes revision-scoped evidence.

The live owner queue, batch claims, revisions, path overlap, commands, outcomes, and dispositions belong in execution evidence rather than this plan. RAG redeclaration remains continuous against the indexed live source. No Step permits a baseline, threshold, new exclusion, suppression, skip, xfail, mock, monkeypatch, tautological assertion, or hidden allowlist to make a red signal disappear. Model routing is stable: Luna max owns audits, type and mechanical work, Terra xhigh owns fixes and refactors, and Sol handles architecture decisions only.

## Steps

## Wave `W07` - activate the rolling ratchet controller

Establish the durable observe, claim, repair, recheck, and evidence loop for the live branch. This Wave activates the operating mechanism only; recurring operation continues as the branch evolves and no codebase-sanity closure is claimed.

### Phase `W07.P20` - observe and claim the live revision

At each observation, capture the current HEAD and gate state, redeclare semantic ownership, and claim only current disjoint work. The live owner queue belongs in execution evidence, never in this plan.

- [ ] `W07.P20.S93` - Observe the current branch revision, dirty paths, ownership context, and gate state, recording revision-scoped evidence without treating any result as a baseline (Luna max audit and mechanical); `.vault/exec/`.
- [ ] `W07.P20.S94` - Redeclare semantic canonical homes and consumer ownership against the indexed live source, persisting only current RAG evidence (Luna max audit); `.vault/audit/`.
- [ ] `W07.P20.S95` - Claim only currently disjoint work and write the live owner queue, starting revision, collision result, and handoff metadata to execution evidence rather than this plan (Luna max audit and mechanical); `.vault/exec/`.
- [ ] `W07.P20.S96` - Amend or codify the standing ratchet rule when observation exposes a durable governance gap, routing architecture-only decisions to Sol and keeping rule maintenance evidence-backed (Luna max audit and mechanical); `.codex/rules/`.

### Phase `W07.P21` - repair and recheck opportunistic batches

Run owner-scoped repairs and focused proofs in opportunistic parallel batches, then rerun affected and global gates. Merge or rebase churn invalidates evidence only for affected batches, which re-enter observation.

- [ ] `W07.P21.S97` - Dispatch opportunistic parallel batches from the live owner queue only when their current path scopes are disjoint, routing fixes and refactors to Terra xhigh, audits and mechanical work to Luna max, and architecture-only decisions to Sol (Luna max coordination); `.vault/exec/`.
- [ ] `W07.P21.S98` - Repair each claimed batch with behavior-preserving changes and real focused proof, without baselines, suppressions, skips, xfails, mocks, monkeypatches, tautologies, or hidden allowlists (Terra xhigh fixes and refactors); `.vault/exec/`.
- [ ] `W07.P21.S99` - Recheck the affected gates and then the global gate matrix for each repaired batch, recording commands, revisions, diagnostics, focused proof, and disposition (Luna max audit and mechanical); `.vault/audit/`.
- [ ] `W07.P21.S100` - When merge or rebase churn changes the observed revision, invalidate only the affected batch evidence, refresh those claims, and preserve unaffected evidence with its revision identity (Luna max audit and mechanical); `.vault/exec/`.

### Phase `W07.P22` - publish a revision-scoped green checkpoint

When the observed revision supports it, publish a checkpoint with all gates green at one HEAD and a repeat confirmation, then continue the recurring loop. This is not permanent codebase-sanity closure.

- [ ] `W07.P22.S101` - Run a revision-scoped green checkpoint only when the observed tree has all required gates green at one HEAD, then repeat the confirmation against that same HEAD before publishing it (Luna max audit and mechanical); `.vault/audit/`.
- [ ] `W07.P22.S102` - Publish the checkpoint evidence with HEAD identity, dirty state, gate outcomes, owner scope, limitations, and unresolved lanes, explicitly describing it as revision-scoped rather than permanent codebase-sanity closure (Luna max audit and mechanical); `.vault/audit/`.
- [ ] `W07.P22.S103` - Return to observation whenever the branch drifts and keep the ratchet loop recurring, completing this plan only after the operating mechanism is activated and never as a claim that future revisions are already green (Luna max audit and mechanical); `.vault/exec/`.

## Parallelization

The phases form a recurring controller: observe and claim, repair and recheck, then publish a revision-scoped green checkpoint and return to observation. Within repair and recheck, batches may run opportunistically in parallel only when their current owner path scopes are disjoint. RAG redeclaration runs continuously at observation and after relevant branch churn.

Merge or rebase churn invalidates only the affected batch evidence; unaffected batch evidence remains valid with its revision identity. A changed or colliding claim returns to observation without invalidating unrelated work. A standing-rule amendment or codification is taken when the controller exposes a durable governance gap, and architecture-only decisions route to Sol. Luna max performs audits, type and mechanical checks, and evidence review; Terra xhigh performs fixes and refactors; Sol is reserved for architecture.

## Verification

The plan is complete when the rolling ratchet mechanism is activated and each activation Step has its execution evidence. Completion of this plan does not assert permanent codebase sanity or close future work.

Each recurring cycle observes the current HEAD and dirty state without a baseline, redeclares RAG ownership, records the live owner queue in execution evidence, and dispatches only current disjoint batches. Terra xhigh repairs and refactors with real behavior proof; Luna max runs audits, type and mechanical checks, affected-gate checks, global gates, and evidence review; Sol handles architecture only. Every batch records its revision, scope, commands, focused proof, affected and global outcomes, and disposition. Branch merge or rebase churn invalidates only affected evidence and sends those claims back through observation.

When the observed revision supports a green result, the controller runs a revision-scoped green checkpoint with all required gates green at one HEAD and a repeat confirmation against that same HEAD before publishing evidence. The checkpoint states warnings, unavailable lanes, limitations, and residual risk explicitly. Any later branch drift starts the next recurring cycle; a checkpoint never becomes a claim that future revisions are already green.
