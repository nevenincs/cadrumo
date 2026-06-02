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

A backgrounded agent's empty or zero-byte output file is not a death signal; transcripts flush at completion. Wait for the completion notification rather than re-dispatching on file size.

Absorb in-scope regressions rather than deferring them. Any regression a campaign's activity touches is in scope and MUST be fixed — there are no "pre-existing, not my problem" deferrals. Run standing read-only review agents over recent commits as a continuous gate.

Lead every dispatch brief with the destructive-git prohibition stated verbatim. "I know this stash/reset is safe" reasoning is the canonical violation; the brief's SAFETY header is what prevents it.
