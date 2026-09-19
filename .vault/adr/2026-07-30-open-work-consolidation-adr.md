---
tags:
  - '#adr'
  - '#open-work-consolidation'
date: '2026-07-30'
modified: '2026-07-30'
body_schema: 'body-v1'
body_hash: 'sha256:29695573610f745669ac167bdc3f33bab7524024da56b308bd1adfea7860ac33'
related:
  - "[[2026-07-30-open-work-consolidation-audit]]"
---

# `open-work-consolidation` adr: `residual open work consolidates into one operator-gated non-coding plan` | (**status:** `accepted`)

## Problem Statement

Six plans were in flight carrying twenty-one open rows, and the open set had stopped being actionable. Per `2026-07-30-open-work-consolidation-audit`, not one of those rows needs code written, nine carry text that is false at `HEAD`, one states a remedy that would take down the runner fleet, and the rest are blocked on an operator act, an upstream defect, or a decision nobody had made. The percentages actively misled: four plans read as one row from completion while the residue was spread thin across all six, so no reader could see the actual sequence of remaining work or tell a cleared blocker from a live one.

A decision is needed now because the failure mode is compounding. Two rows had been reading as blocked on a repository that existed, and the correction only surfaced when a reader distrusted the text; the same class of drift already degraded a governance gate two days earlier. Every additional day of divergence makes the plans a worse guide than reading the forge directly, which defeats their purpose.

## Considerations

- Twenty of twenty-one rows are non-coding, and the mandatory semantic-discovery gate was unavailable this session, which would have refused coding work outright — so a non-coding flow is unblocked by an outage that would stall a coding one (`2026-07-30-open-work-consolidation-audit`, no-coding-work-outstanding).
- Roughly thirteen rows stand behind a single variable and a single approval, so the residue is a chain, not a set (same audit, publish-gate-collapsed).
- Two rows cannot close on their own terms: one waits on an instrument that has never worked, one on a single-use second factor (same audit, rag-instrument-never-recovered).
- The project rule against marking a step complete without an execution record binds every closure here, and the deferral clause of that rule is what makes a documented carry-forward legitimate rather than a quiet abandonment.
- Marking a row complete because it is no longer worth doing would be the dishonest closure this project's own honesty-review discipline exists to catch.

## Considered options

- **Leave the six plans as they are and work the rows in place.** Zero migration cost, and each row stays with its originating grounding. Rejected: the audit's central finding is that the scattered form is what hid the drift, and correcting text without consolidating leaves the next reader with the same six-way lookup and the same misleading percentages.
- **Close all six plans and track the residue outside the vault.** Fastest to a clean board. Rejected: it discards the execution-record chain that makes closure auditable, and the residue is exactly the work most likely to be misremembered.
- **One consolidated plan admitting any kind of work, coding included.** Simple rule, one home. Rejected: it re-couples the flow to the discovery gate, so a semantic-index outage would stall operator-gated rows that have nothing to do with code.
- **One consolidated non-coding plan, originating plans closed with documented carry-forwards.** Chosen. Preserves the record, collapses the lookup to one document, and keeps the flow structurally independent of the discovery gate.

## Constraints

The flow depends on acts outside the tree and outside any agent's reach: repository settings that hold the publication variable and the environment approval, host configuration for a native runner and a sandbox feature, in-application interactions in two client products, an upstream repository's release process, and one live authentication approval bound to an operator device. None can be verified from the worktree, so the plan must state its preconditions as operator instructions and its verifications as forge-observable facts.

Two rows carry an unresolved dependency of a different kind. The semantic-sweep row's instrument degraded to zero coverage while reporting success, and a rebuild did not converge it, so its repair is an infrastructure task of unknown size rather than a step with a known shape. The published-plugin defect depends on a package that does not yet exist on the index, so it cannot be fully closed before the first publication even though its diagnosis is complete.

Because minted evidence lives in a git-ignored directory, no row in this plan may treat a local artefact as its verification.

## Implementation

The originating plans are corrected first and closed second. Correction rewrites the nine rows whose text is false at `HEAD` through the owning plan verbs, with the container-mode row treated as a hazard rather than an inaccuracy and rewritten to name the native-runner blocker that actually applies. Only then does closure proceed, so no plan closes over text that would mislead a later reader.

Rows that can close on existing evidence close in place, each with an execution record naming the run identifier and the commit whose ancestry was checked, never a local path. The semantic-sweep row is the one exception to closing only what is done: it closes as *superseded*, recording that its instrument never became trustworthy and that the discovery need was met by a structural-AST substitute, with the residual repair-and-rerun carried forward. The distinction between superseded and satisfied is load-bearing and is stated in its record.

Rows that cannot close are migrated, and migration means the row is REMOVED from its originating plan once this plan carries it. An earlier revision of this record ruled that such rows stay in place with a carry-forward annotation, and that form was implemented first and then rejected on inspection: annotating left five plans in flight alongside this one and the same work tracked in two documents at once. A forked fact is precisely the drift mechanism this decision exists to remove, and the audit's own evidence is that the fleet's worst inaccuracy arose from two plans disagreeing about one fact with neither authoritative. Removal is therefore not tidying but the substance of the migration. Nothing is marked complete that is not complete, the row text survives in version history, and each originating plan records in its Description which rows left and where they went, so the scope a campaign originally carried stays recoverable.

The consolidated plan then carries every remaining row as one ordered flow, grouped by the operator act that releases it rather than by originating campaign, so the sequence reads top to bottom. It admits no coding work by construction: a row discovered to need code leaves this plan for a coding campaign with a semantic-discovery gate in front of it, rather than quietly widening this one.

## Rationale

The knockout criterion is independence from the discovery gate. Per the audit, the residue is entirely non-coding, and this session demonstrated that an unavailable semantic index refuses coding work outright while leaving operator-gated and documentation work untouched. A plan that admits both kinds couples the unblocked majority to the blocked minority for no benefit; a plan that admits only non-coding work can always be driven forward, which is the property the last several weeks of stalling lacked.

The consolidation also fixes the specific mechanism the audit identified. Drift went unnoticed because two plans disagreed about the same fact and neither was authoritative — one recorded the shared repository as created while the other kept citing its absence. A single carrier for live work removes the second home a fact can live in, which is the same single-declaration discipline this project already applies to terminology and registry authority.

Closing plans with carry-forwards rather than deleting rows preserves the audit trail that makes a later reader able to distinguish work that was done, work that was deliberately deferred, and work that was abandoned. The alternative that looked tidier destroys precisely that distinction.

## Consequences

The board becomes honest: five plans reach a real terminal state, one 287-row campaign can finish, and the remaining work reads as a single ordered sequence whose next action is unambiguous. The operator gains a runbook rather than a six-way reconciliation exercise, and the largest cascade in the fleet is exposed as one variable and one approval.

The honest difficulties. A consolidated plan concentrates risk: if its ordering is wrong the whole flow reads wrong, where six plans failed independently. Closing the semantic-sweep row as superseded means the codebase carries no current semantic-duplication sweep, and the substitute covered discovery rather than that row's own instrument requirement — a gap that is now recorded rather than latent, but still a gap. Carry-forward annotations are only as good as the reader who follows them, and this audit exists because such text was not followed.

Two pitfalls to watch. Migrating a row can look like progress when nothing changed but its address, so the plan's rows must state verifications, not intentions. And a non-coding plan invites scope creep the moment a row turns out to need a small fix; the rule that such a row leaves the plan is what keeps the discovery gate from being bypassed by convenience.

The pathway this opens is a fleet whose remaining work is bounded by operator availability rather than by uncertainty about what remains — which is the precondition for a first canonical release.
