---
name: aeat-agent-orchestration
trigger: always_on
---

# AEAT agent orchestration, audit cadence, and campaign close

Governs dispatch, the standing audit, and campaign close. Companion to
`aeat-worktree-safety` (the commands).

## Dispatch

- Drive campaigns through a persistent, role-based team resumed by name; do not
  spawn one-shot agents for work a standing role owns. One issue per
  delegation; handovers agent-agnostic (never hard-code a model vendor or
  launcher command into project instructions).
- **Discover with a swarm, not solo.** For any non-trivial code-location,
  duplication or cross-domain question: parallel discovery agents, output
  treated as inventory to confirm, paired with a targeted `rg` for known
  symbols.
- **Lead every brief with the destructive-git prohibition stated verbatim AND
  the sanctioned alternative** — a prohibition alone leaves the agent to invent
  one under pressure.
- **Drive autonomously.** Adjudicate, persist decisions in `.vault/`, and do
  not stall on choices resolvable from the code, the rules, or sensible
  defaults. Suite runs are rolling checkpoints; never cap work as "final".
- **Before dispatching a Step:** `git log --grep` and plan status — Steps land
  in parallel and may already be done. **Before a coder's first edit:**
  `git diff -- <file>`; abort on non-authored WIP.
- **Re-read HEAD before recommending or acting on any finding** — a peer fix
  can land between investigation and report, so recompute the "still-a-gap"
  conclusion at report time. A backgrounded agent's empty output file is not a
  death signal; transcripts flush at completion.
- **Absorb in-scope regressions.** No "pre-existing, not my problem".
- **Work tracking:** no GitHub project board — issues, live worktrees and the
  vault pipeline only. An issue is actively worked only when a worktree AND a
  delegation exist. Balance the AEAT remote-synchronisation and financial-input
  tracks; bind financial-input work to the Transaction Data Pipeline step it
  serves; preserve provenance from ingest through handoff; Google Sheets is a
  one-way export mirror, never an authority.

## Audit cadence

Run the multi-agent audit swarm on **event triggers**: before a release cut
that crossed a domain boundary or persisted a new record type; after a
structural refactor touching more than two domain subpackages; every six to
eight commits on a long branch otherwise.

**Eight axes, one agent each:** calculation-engine grounding,
persistence-boundary identity, cross-domain handoffs, export/import fidelity,
workflow and CLI surface, selector/binding drift, semantic
functionality-cluster overlap, runtime import-graph coupling. Reasoning tier
for the four structural axes (calculation engine, cross-domain handoffs,
selector/binding drift, semantic overlap); cheap tier for the breadth four.

- **Axis 7, semantic overlap:** find by MEANING every site implementing a
  concept; classify true-duplication vs constraint-shape-divergent; confirm
  consumers import the canonical implementation; nominate a canonical home
  where two or more substitutable sites exist without one. Pair with a
  targeted `rg` for known canonical symbols.
- **Axis 8, runtime coupling:** grimp over the *executed* import graph (denser
  than import-time — deferred function-local imports hide cycles rather than
  remove them); diff cross-layer and cycle edges against the static picture.
  There is NO sanctioned inventory of function-local first-party edges to diff
  against: report such an edge on the graph difference alone, marked
  **unclassified** — never imply an allowlist cleared the rest.
- **Substitutability pre-filter** before any "X where Y exists" flag: Y's
  constraint shape must be a superset of X's. If Y carries constraints
  (min_length, pattern, max_length, value-format) that X does not, the site is
  NOT promotable — exclude it or document the mismatch.
- **Persist every finding** as `.vault/audit/yyyy-mm-dd-<axis>-swarm-audit.md`:
  third-level headings with pathway label, `file:line`, what is lost, concrete
  remediation. Reports must not modify production code. **Action every
  finding:** structural fix + roundtrip test, a wontfix vault note, or a linked
  follow-up task.
- **Swarm output is inventory, not gospel** — sub-agents miss things and
  hallucinate `file:line`. Verify every finding against current code first.

## Campaign close

- Every close triggers a **fresh-context honesty review** against the closure
  summary BEFORE declaring structural completeness (an independent reviewer
  dispatch; a "review as if you just inherited it" persona switch; or a
  declarative-vs-action curate pass). Persist as a vault audit; track every
  item as a Step with a verification gate. **Not complete until honest-pass
  items are closed with verification or formally deferred with a reference.**
- **A campaign cannot narrow its own completion criterion.** Beside every
  scope-narrowing note, write what the standing goal still asks for that it
  excludes.
- **No plan step marked complete without a matching exec record**, or a close
  audit recording the deferred carry-forward — otherwise delivered-as-specified,
  delivered-narrower and recorded-but-not-implemented wear the same checkbox.
- **An ADR amendment ruling on CODE is not self-executing.** Open the
  implementing rows in the SAME action as the amendment and grep the source for
  prose describing the old state as pending. "The ADR says X" is not evidence
  that X is true of the tree.
