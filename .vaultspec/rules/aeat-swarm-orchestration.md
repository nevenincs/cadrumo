# AEAT agent orchestration and delivery

Governs how agents are dispatched and coordinated. Companion to
`aeat-git-worktree-safety` (the commands) and `aeat-swarm-audit-cadence` (the
periodic audit).

## Dispatch

Drive campaigns through a persistent, role-based team — legal authority, ADR
specialist, coders, reviewers, commit bot — resumed by name. Resume a standing
teammate to reuse its context; do not spawn fresh one-shot agents for work a
standing role owns.

**Discover with a swarm, not solo.** Solo search is unreliable here. For any
non-trivial code-location, duplication, or cross-domain question, dispatch
parallel discovery agents, treat their output as inventory to confirm, and pair
broad-concept discovery with a targeted `rg` pass for known symbols.

**Lead every brief with the destructive-git prohibition stated verbatim AND the
sanctioned alternative.** A brief that states only the prohibition leaves the
agent to invent one under pressure.

**Drive autonomously.** Long-running campaigns run open-ended: adjudicate,
persist decisions in `.vault/`, and do not stall on confirmation for choices
resolvable from the code, the rules, or sensible defaults. Treat suite runs as
rolling checkpoints; never cap work as "final" or "done".

## Before touching anything

Before dispatching a plan Step, grep `git log --grep` and check plan status — the
team lands Steps in parallel and a Step may already be done. Before a coder's
first edit, `git diff -- <file>` and abort on non-authored WIP.

**Re-read HEAD before recommending or acting on any finding.** A peer fix can
land between investigation and recommendation, so the *facts* stay valid while
the "still-a-gap" *conclusion* must be recomputed at report time. Run
`git log -1 -- <file>`, re-read at HEAD, and abort if a peer already closed it.

A backgrounded agent's empty output file is not a death signal — transcripts
flush at completion. Wait for the completion notification.

**Absorb in-scope regressions.** Any regression a campaign's activity touches is
in scope; there are no "pre-existing, not my problem" deferrals.

## Work tracking

There is no GitHub project board. Track work through GitHub issues, live git
worktrees, and the vault pipeline only. Treat an issue as actively worked only
when a worktree **and** a delegation exist for it. Do not reintroduce a board,
and do not mark charters, placeholders, or intent as active execution.

Delegate one issue at a time and keep handovers agent-agnostic — never hard-code
a specific model vendor or launcher command into project instructions. Balance
capacity across the AEAT remote-synchronisation track and the financial-input
track; do not starve either. Bind financial-input work to the Transaction Data
Pipeline step it serves, preserve provenance from ingest through handoff, and
treat Google Sheets as a one-way export mirror, never an authority.
