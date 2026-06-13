---
tags:
  - '#adr'
  - '#agent-rule-consolidation'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-06-01-agent-rule-consolidation-research]]"
---



# `agent-rule-consolidation` adr: `Drain agent memory into condensed rules; sweep worktree scratch` | (**status:** `accepted`)

## Problem Statement

Result of a hygiene audit of the shared worktree. Durable agent guidance is
split across two stores: 17 condensed project rules (loaded into every agent's
context) and 38 free-form per-project memory notes plus an 8 KB index that also
loads every session. The memory store largely duplicates the rules, carries
transient campaign state, and is the non-preferred surface. The rules
themselves carry point-in-time statistics and a dated campaign reference that
have gone stale against the live codebase. Untracked agent scratch pollutes
`git status` because `.gitignore` does not match the patterns agents actually
emit.

## Considerations

The worktree is shared by concurrent campaigns holding uncommitted WIP; any
sweep must touch only ephemeral root scratch and never peer deliverables.
Memory lives outside the repo (`~/.claude/...`), so draining it is not a git
operation and carries no collision risk. Rule corrections must land on the
`.vaultspec/rules/rules/project/` **source** and propagate via
`vaultspec-core sync`; editing the generated `.claude/rules/` copy is reverted by
the next sync. Rules load into every context, so additions must stay terse —
the goal is a smaller, truer rule set, not a larger one.

## Constraints

No new dependencies. Bounded by the destructive-git prohibition: explicit-path
staging only, no `git clean`/`stash`/`reset`. The temp sweep deletes only
untracked root scratch older than ~24h (today's files may be in active use).
Provider outputs (`AGENTS.md`, `GEMINI.md`, `.claude/rules/`) are sync-managed
and out of scope for hand edits.

## Implementation

Three coordinated sweeps. **Worktree:** extend `.gitignore` with a scratch block
matching the emitted patterns, then delete the stale dead scratch.
**Rules:** correct the two truthfulness-rot spots (drop the frozen "53%/26%"
statistic from `core-struct-docstring-links`; replace the dated campaign
reference and frozen percentages in `aeat-campaign-close-honesty-review` with
durable generic phrasing) and tighten the narrative bloat in
`aeat-git-worktree-safety` while preserving its command lists verbatim.
**Memory:** codify the durable shared-worktree-orchestration lessons into one new
compact rule `aeat-swarm-orchestration` and fold the audit-discipline lessons as
terse additions to `aeat-quality-gates`; then delete all 38 memory notes and
reset `MEMORY.md` to a near-empty index pointing at the rule system. Finish with
`vaultspec-core sync` and `vault check all`.

## Rationale

The memory store violates the project's own centralisation rule
(`aeat-vaultspec-centralisation`: keep durable agent guidance in the rule system,
treat provider/memory surfaces as generated). Draining it removes a recurring
8 KB context load and a duplication maintenance burden, and the few genuinely
durable lessons survive as enforceable rules. Fixing rot keeps the rules
trustworthy; an agent that cannot trust a rule's specifics ignores the rule.

## Consequences

Smaller, truer rule set and a near-empty memory store that future sessions do
not have to reconcile. Risk: a durable lesson could be lost in the drain — the
new rule and the augmentations are the mitigation, and the deleted notes remain
recoverable from this ADR's inventory. The temp sweep is conservative by design;
today's scratch persists until a later pass. Future rule corrections by any agent
must follow the source-then-sync discipline this ADR records.

## Codification candidates

- **Rule slug:** `aeat-swarm-orchestration`.
  **Rule:** In the shared multi-campaign worktree, use a persistent role-based
  agent team resumed by name (not one-shot task agents), prefer a parallel
  discovery swarm over solo search, check `git log` before dispatching a step,
  treat a backgrounded agent's empty output file as alive, absorb in-scope
  regressions rather than deferring them, and treat suite runs as rolling
  checkpoints rather than a terminal "complete".

- **Rule slug:** `aeat-vaultspec-centralisation` (existing, augment).
  **Rule:** Correct project rules on the `.vaultspec/rules/rules/project/`
  source and propagate with `vaultspec-core sync`; never hand-edit the generated
  `.claude/rules/`, `AGENTS.md`, or `GEMINI.md` provider outputs.
