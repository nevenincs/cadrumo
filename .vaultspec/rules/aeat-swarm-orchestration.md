# AEAT swarm orchestration

This worktree is a shared workspace driven by many concurrent campaign agents.
These disciplines govern dispatch and coordination. They are the durable
counterpart to `aeat-git-worktree-safety` (which governs the commands) and
`aeat-swarm-audit-cadence` (which governs the periodic audit).

**Drive campaigns through a persistent, role-based agent team** — legal
authority, ADR specialist, coders, reviewers, commit bot — resumed by name via
the team-dispatch messaging tools. Resume a standing teammate to reuse its
accumulated context; do not spawn fresh one-shot agents for work a standing role
already owns.

**Discover with a swarm, not solo.** Solo single-agent search is unreliable
here. For any non-trivial code-location, duplication, or cross-domain question,
dispatch parallel discovery agents and treat their output as inventory to
confirm, never as gospel. Pair broad-concept agent discovery with a targeted
`rg` pass for known symbols.

**Drive autonomously.** Long-running reconciliation and hardening campaigns run
open-ended. The coordinator adjudicates, persists decisions in `.vault/`, and
does not stall on confirmation for choices it can resolve from the code, the
rules, or sensible defaults. Treat suite runs as rolling checkpoints. Never cap
work as "final" or "done"; keep the audit-fix-review cycle running.

**Before dispatching a plan Step**, grep `git log --grep` and check plan status
— the team lands Steps in parallel and a Step may already be done. **Before a
coder's first edit to a file**, `git diff -- <file>` and abort on non-authored
WIP.

**Re-read HEAD before recommending or acting on any finding.** This is the
read-side companion to the abort-on-WIP edit gate: in this fast-landing tree a
peer fix can land between an agent's investigation and its recommendation, so
the investigation *facts* stay valid while the "still-a-gap" *conclusion* must
be recomputed against HEAD at report time. Immediately before recommending an
edit, run `git log -1 -- <file>`, re-read the file at HEAD, and abort the
recommendation if a peer commit already closed the gap.

**A backgrounded agent's empty or zero-byte output file is not a death signal**
— transcripts flush at completion. Wait for the completion notification rather
than re-dispatching on file size.

**Absorb in-scope regressions rather than deferring them.** Any regression a
campaign's activity touches is in scope and MUST be fixed; there are no
"pre-existing, not my problem" deferrals. Run standing read-only review agents
over recent commits as a continuous gate.

**Lead every dispatch brief with the destructive-git prohibition stated
verbatim, and with the sanctioned alternative.** "I know this stash or reset is
safe" is the canonical violation, and a brief that states only the prohibition
without naming the apply-cached drive leaves the agent to invent one under
pressure.
