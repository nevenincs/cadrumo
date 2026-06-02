---
name: aeat-swarm-orchestration
trigger: always_on
---

# AEAT swarm orchestration

This worktree is a shared workspace driven by many concurrent campaign agents. These disciplines govern how agents are dispatched and coordinated. They are the durable counterpart to `aeat-git-worktree-safety` (which governs the commands) and `aeat-swarm-audit-cadence` (which governs the periodic audit).

Drive campaigns through a persistent, role-based agent team — legal-authority, ADR-specialist, coders, reader/reviewers, commit-bot — resumed by name via the team-dispatch messaging tools. Resume a standing teammate to reuse its accumulated context. Do not spawn fresh one-shot task-named agents for work a standing role already owns.

Discover with a swarm, not solo. Solo single-agent search is unreliable in this codebase. For any non-trivial code-location, duplication, or cross-domain question, dispatch parallel discovery agents and treat their output as inventory to confirm, never as gospel. Pair semantic RAG discovery with a targeted `rg` pass for known symbols.

Drive autonomously. Long-running reconciliation and hardening campaigns run open-ended without a human in the loop. The coordinator adjudicates and persists decisions in `.vault/`, and does not stall on confirmation for choices it can resolve from the code, the rules, or sensible defaults. Treat suite runs as rolling checkpoints. Never cap work as "final", "complete", or "done"; keep the audit → fix → review cycle running.

Before dispatching a plan Step, grep `git log --grep` and check plan status — the team lands Steps in parallel and a Step may already be done. Before a coder's first edit to a file, `git diff -- <file>` and abort on non-authored WIP — peers may be mid-edit in the same file.

Re-read HEAD before recommending or acting on any finding. This is the read-side companion to the abort-on-WIP edit gate above: in this fast-landing shared worktree a peer fix can land between an agent's investigation and its recommendation, so the investigation *facts* stay valid but the "still-a-gap" *conclusion* MUST be recomputed against HEAD at report/action time. Immediately before recommending an edit or acting on a finding that names a file, run `git log -1 -- <file>` and re-read the file at HEAD; abort the recommendation if a peer commit already closed the gap. This churned the multi-year-renta campaign twice: a "GO edit the test" directive fired against the #38 M100 enrollment test that was already full-calc at HEAD (commit `5ac27ed5c`), and a #42 stale read concluded "M369 is already sound / finding mis-bundled" from a copy read before `627f0aa05` landed, when in fact both M309 and M369 were `data_fidelity` and both were upgraded together. The code-reviewer flagged the version-skew explicitly; see audit `2026-06-02-modelo-multiyear-renta-audit`.

A backgrounded agent's empty or zero-byte output file is not a death signal; transcripts flush at completion. Wait for the completion notification rather than re-dispatching on file size.

Absorb in-scope regressions rather than deferring them. Any regression a campaign's activity touches is in scope and MUST be fixed — there are no "pre-existing, not my problem" deferrals. Run standing read-only review agents over recent commits as a continuous gate.

Lead every dispatch brief with the destructive-git prohibition stated verbatim. "I know this stash/reset is safe" reasoning is the canonical violation; the brief's SAFETY header is what prevents it.
