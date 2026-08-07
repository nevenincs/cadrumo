# AEAT agent orchestration, audit cadence, and campaign close

Governs how agents are dispatched, how the standing audit runs, and what closing
a campaign requires. Companion to `aeat-worktree-safety` (the commands).

## Dispatch

Drive campaigns through a persistent, role-based team — legal authority, ADR
specialist, coders, reviewers, commit bot — resumed by name. Resume a standing
teammate to reuse its context; do not spawn fresh one-shot agents for work a
standing role owns. Delegate one issue at a time and keep handovers
agent-agnostic — never hard-code a model vendor or launcher command into project
instructions.

**Discover with a swarm, not solo.** Solo search is unreliable here. For any
non-trivial code-location, duplication or cross-domain question, dispatch
parallel discovery agents, treat their output as inventory to confirm, and pair
broad-concept discovery with a targeted `rg` for known symbols.

**Lead every brief with the destructive-git prohibition stated verbatim AND the
sanctioned alternative.** A brief that states only the prohibition leaves the
agent to invent one under pressure.

**Drive autonomously.** Long-running campaigns run open-ended: adjudicate,
persist decisions in `.vault/`, and do not stall on confirmation for choices
resolvable from the code, the rules, or sensible defaults. Treat suite runs as
rolling checkpoints; never cap work as "final" or "done".

**Before dispatching a Step**, grep `git log --grep` and check plan status — the
team lands Steps in parallel and a Step may already be done. **Before a coder's
first edit**, `git diff -- <file>` and abort on non-authored WIP.

**Re-read HEAD before recommending or acting on any finding.** A peer fix can
land between investigation and recommendation, so the *facts* stay valid while
the "still-a-gap" *conclusion* must be recomputed at report time. A backgrounded
agent's empty output file is not a death signal — transcripts flush at
completion.

**Absorb in-scope regressions.** Any regression a campaign's activity touches is
in scope; there are no "pre-existing, not my problem" deferrals.

**Work tracking:** there is no GitHub project board. Track work through issues,
live worktrees and the vault pipeline only. Treat an issue as actively worked
only when a worktree **and** a delegation exist. Balance capacity across the AEAT
remote-synchronisation track and the financial-input track; bind financial-input
work to the Transaction Data Pipeline step it serves, preserve provenance from
ingest through handoff, and treat Google Sheets as a one-way export mirror, never
an authority.

## Audit cadence

Run the multi-agent audit swarm on **event triggers**: before a release cut that
crossed a domain boundary or persisted a new record type; after a structural
refactor touching more than two domain subpackages; and every six to eight
commits on a long-running branch when no other trigger has fired.

**Eight axes**, one agent each: calculation-engine grounding, persistence-boundary
identity, cross-domain handoffs, export/import fidelity, workflow and CLI
surface, selector and binding drift, semantic functionality-cluster overlap, and
runtime import-graph coupling. **Match the model to the axis** — the reasoning
tier for the four needing deeper structural analysis (calculation engine,
cross-domain handoffs, selector/binding drift, semantic overlap), the cheap tier
for the four breadth-oriented ones.

**Axis seven, semantic overlap**, runs as a parallel discovery pass: it finds by
MEANING every site implementing a functional concept, classifies the set as a
true duplication cluster or a constraint-shape-divergent one, confirms consumers
import the canonical implementation, and nominates a canonical home where none
exists but two or more substitutable sites do. Pair every sweep with a targeted
`rg` for known canonical symbols.

**Axis eight, runtime coupling**, runs a grimp pass over the *executed* import
graph, not the import-time graph the layered linter audits. The runtime graph is
denser because many function-local imports are deferred to break cycles, and a
cycle "fixed" by deferring an import is hidden rather than removed. Diff grimp's
cross-layer and cycle edges against the static picture. **There is no sanctioned
inventory of function-local first-party edges to diff against**, so report such an
edge on the graph difference alone and state that the finding is
**unclassified** — never imply an allowlist cleared the rest.

**Apply the substitutability pre-filter before flagging any "X where Y exists"
violation.** Verify Y's constraint shape is a superset of — more permissive than —
X's current constraint. If Y carries additional constraints (min_length, pattern,
max_length, value-format) that X does not, the site is NOT promotable: exclude it
or document the mismatch. Without this filter the false-positive rate is
overwhelming.

**Persist every finding** as one `.vault/audit/yyyy-mm-dd-<axis>-swarm-audit.md`,
findings as third-level headings with a pathway label, `file:line`, what is lost,
and a concrete remediation. Reports must not modify production code. **Action
every finding** as a structural fix paired with a roundtrip test, a vault note
recording the wontfix rationale, or a linked follow-up task.

**Treat swarm output as inventory, not gospel.** Sub-agents miss things and
occasionally hallucinate `file:line` coordinates. Verify every finding against
current code before action.

## Campaign close

Every campaign close MUST trigger a **fresh-context honesty review** against the
closure summary BEFORE the campaign is declared structurally complete. An agent
driving execution routinely self-reports "complete" while a substantial fraction
is still structurally incomplete.

The review may be an independent code-reviewer dispatch given the summary, ADR
and commit ranges; a persona switch prompted with "review the campaign as if you
had just inherited it and list what is missing, vague, or
assumed-but-unverified"; or a curate pass scanning for declarative-versus-action
gaps — Steps saying "investigate" with no verification gate, ADR claims with no
matching test, audit recommendations not tracked as Steps.

Persist the output as a vault audit document and track every item as a new Step
with a verification gate. **The campaign is NOT complete until honest-pass items
are closed with verification or formally deferred with a follow-up reference.**
Recurring multi-item discoveries per pass are expected; the gate is whether a
fresh review ran before closure was declared.

**A campaign cannot narrow its own completion criterion.** Scoping work out is a
decision the campaign records about itself; it does not move the standing goal,
and measuring "complete" against the narrowed version is invisible from inside
precisely because the narrowing is documented and reads as rigour. Write beside
every scope-narrowing note what the standing goal still asks for that it
excludes.

**A plan step must not be marked complete without a matching exec record**, or a
close audit explicitly recording why it is a deferred carry-forward. Three states
otherwise wear the same checkbox: delivered as specified, delivered narrower, and
recorded-but-not-implemented.

**An ADR amendment that rules on CODE is not self-executing.** The amending
Step's deliverable is "the record is correct", which completes honestly while the
implementation debt it created has no owner and no row — and every later reader
sees the ruling as in force while HEAD carries the rejected design. Open the
implementing rows in the **same action** as the amendment, and grep the source
for prose describing the old state as pending. **"The ADR says X" is not evidence
that X is true of the tree.**
