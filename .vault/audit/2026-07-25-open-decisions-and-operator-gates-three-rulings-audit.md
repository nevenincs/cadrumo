---
tags:
  - '#audit'
  - '#open-decisions-and-operator-gates'
date: '2026-07-25'
modified: '2026-07-26'
related:
  - "[[2026-07-25-open-decisions-and-operator-gates-plan]]"
  - "[[2026-07-25-code-dedup-sweep-adr]]"
  - "[[2026-07-25-reconcile-evidence-relocation-adr]]"
  - "[[2026-07-24-evidence-revision-identity-adr]]"
---

# `open-decisions-and-operator-gates` audit: `ruling S01-S03, and what moved at HEAD`

## Scope

Steps S01, S02 and S03 of this feature's plan: three decision records sitting at
`proposed` with no plan and no execution records, leaving the work they govern
invisible to plan status. Each was read together with its research and audit
companions, then every load-bearing claim was re-established against the tree at
HEAD `7058ef827f` before ruling. Steps S04 through S10 are operator-only and were
not touched.

Semantic search was unavailable throughout. The code index was truncated — roughly
1027 chunks against roughly 4546 files — while reporting `degraded_reasons: []`,
so the discovery mandate's refuse-if-unavailable clause never fires and a miss
carries no evidential weight whatever. Substituted throughout: exhaustive `rg`
sweeps, full reads of both sides of every site, and git history for dating and
attribution. Every count below was taken at HEAD rather than carried from the
records under review.

This document also stands in for the three execution records those steps would
otherwise carry. The feature is a coordination plan with no ADR of its own and
never will have one — it tracks decisions and operator gates rather than
executing a decision — so the lifecycle gate refuses an exec record for it.
Fabricating an ADR that decides nothing purely to open that gate would have
produced exactly the hollow artefact this campaign exists to remove. The
plan-closure rule anticipates this: a step may close against a close audit that
records the evidence, which is what follows.

## Findings

### s01-governs-no-shipped-work | high | the premise that dedup work landed against this record is wrong on the dates

S01's record was believed to govern dedup work already in the tree, which would
have made it a retro-ruling on shipped code. It does not. The dedup commits
carrying its feature tag — `refactor(adapters): dedup storage/inbound clone
clusters (Batch A G1)` at `8bf229716e` through `e9a3c35abe` — landed 2026-07-21.
The record was scaffolded 2026-07-25 at 16:39 in `f8fa62ef11`, four days later.
Those commits are jscpd clone-cluster extraction belonging to the
duplication-evidence-repair campaign, and they share the feature tag only because
`vault add adr` has no `--topic` flag, so there is exactly one ADR filename slot
per feature per date — a hazard the companion audit records explicitly. The
record's actual subject is entirely unimplemented. It is a forward decision, and
nothing needed reconciling between record and reality.

The durable hazard is the inference itself: a reader seeing dedup commits and an
ADR under one tag will reasonably conclude the ADR ruled them. Allocate a distinct
feature tag per decision, or scaffold ADRs serially from the coordinator.

### s01-subject-confirmed-live | medium | twenty sites, and the vacuity proof holds with one correction

All twenty inner-envelope read paths carry the loose `>` comparison at HEAD,
enumerated site by site in the record. Only one line reference had drifted. The
vacuity proof was re-derived rather than accepted: the `Envelope.schema_version`
floor is confirmed `Field(ge=1)`, so the below-current region is empty and the two
predicates coincide today.

One correction. The namespace count is 67, not 66 — sixty-six declare the shared
V1 constant and a sixty-seventh declares its own blob-manifest constant, which
happens to equal 1. The argument survives on a coincidence of value rather than a
shared authority, so the gate the record mandates must assert a relation — each
namespace's declared version against the version its readers compare — rather than
the literal 1, which a legitimate future per-namespace bump would red for the
wrong reason.

A second observation strengthens the case and was not visible from the inventory:
equality is already the majority shape across the substrate, holding at nine
further persisted read sites. The twenty are a minority residue of an older
spelling rather than a competing convention of equal standing.

### s02-overflow-shape-resolved-around-its-exception | high | two of three open items closed since the record was written

S02's record closes by naming three open items. Two closed between its authoring
and this ruling, both by peer commits. The joined-id pair in the
transaction-removal event is fixed — the payload now carries counts, and the
in-code comment reproduces the research's own 519-character arithmetic and records
why nothing is lost. The `source_ref` 512-against-500 inconsistency is fixed by a
change broader than the item as recorded: it found a second, unbounded producer
the record missed, and that one was the reachable one.

The recomputation is decisive rather than incidental. Every instance the
bounded-metadata remedy could close has now been closed by it, each in its own
commit, and the residue is exactly the one instance where that remedy is lossy —
because the reconcile detail is the only copy. The systemic pattern and the
reconcile exception are no longer competing readings of the evidence: the pattern
has resolved itself around the exception, which is what settled the ruling toward
a dedicated store.

### s03-stranded-work-unit-confirmed-and-cheaper-than-recorded | high | the fix is enrolment under a refusal shape the same module already has

S03's sharper defect is live and unchanged: work-unit creation derives the id,
finds the existing record and returns it with no state check, so a discarded unit
is handed back and every downstream verb then denies it exists. Confirmed by
reading the function at HEAD.

What the record did not note is that the fix is cheaper than it appears. The same
module already refuses a discarded unit instructively eleven lines below, and
refuses a second discard three lines further on. The refusal vocabulary, the error
branch and the precedent all exist — creation is the one member of the family that
omits the check. A related asymmetry sharpens the statement: the listing surface
already hides discarded units by default, so discovery and creation currently
disagree about whether a discarded unit exists.

The evidence-exclusion claim was also re-verified. The revision id deriver's
signature and hashed payload carry no evidence reference, and its docstring
publishes the content-addressing contract — so folding evidence in would reverse a
published invariant rather than fix an oversight.

### rulings-and-plans | info | three accepted, three plans, twenty-one steps

All three ruled `accepted`, each with its Implementation section made concrete
enough to plan from, and each now carried by a plan so the work is visible in
plan status. Six steps for the inner-envelope tightening, eight for the reconcile
relocation, seven for the discard refusal and supersede transition.

No objection was deleted from any record. Where this ruling disagreed with
reasoning already present — the counter-argument for bounded metadata in S02, the
evidence-digest option in S03 — it was refuted in place and the original left
standing. Corrections were appended beside the reasoning they correct rather than
replacing it, so a later reader can see both what was believed and what was
measured.

### execution-halted-on-the-discovery-gate | critical | the index collapsed a second time, so the remaining new-mechanism work is refused

Execution of the three plans stopped short of the supersede transition and the
reconcile store, and the reason is the mandatory discovery gate rather than
effort or judgement.

The code index collapsed a second time during this session: 902 chunks against
3,681 tracked source files, roughly one to two percent coverage, while
`degraded_reasons` stayed empty. Because the service reports itself healthy, the
discovery mandate's refuse-if-unavailable clause never fires on its own — the
gate silently degrades from search-by-meaning into returning a handful of
arbitrary files, which is the incident this campaign already recorded as
critical.

It was confirmed by probe, not by the counter alone. The decisive query — "open a
new draft calculation revision from a finalized one", which is precisely the
concept the supersede transition would introduce — returned five chunks of one
unrelated repository module at scores from 0.06 down to 0.013, with no candidate
owner of the concept anywhere in the result. A sibling probe on export-evidence
refusal returned a CLI risk table and a constants module. Two unrelated probes
collapsing onto irrelevant files is the documented tell.

The work refused is exactly the class the rule protects: a new lifecycle
transition, a new verb, a new persisted namespace and a new event type. An
unsearched edit there cannot establish that no canonical owner already exists
under a name nobody thought to grep, which is how duplicate authorities enter
this codebase. The rule states that this refusal stands even when a hook, goal or
plan step mandates the work, and a goal directive was in force — so this is the
pressure case the rule was written for rather than an edge of it.

The service was deliberately not restarted and no reindex was requested: a
restart discards the in-progress job and induces a perpetual-reindex state. The
watcher is armed while a large fleet writes continuously, so each pass truncates
and restarts. One recovery to 68,502 chunks was observed mid-session and used —
validated by two unrelated probes returning disjoint correct owners before any
code was written — and it did not hold.

### remaining-steps-taken-up-by-the-fleet | info | the rulings are being executed by peers, which is the handover working

The remaining steps are not idle. Peer agents delivered the predicate, the
twenty-site sweep and the structural gate; a peer is adding the reconciliation
records namespace; and untracked drafts exist for both deferred rulings this
campaign carried forward — the bucket-manifest durability decision and the
bucket-event payload-bounding decision, each with its own survey audit. That is
the intended outcome of ruling rather than building: the decisions became visible
in plan status and the fleet picked them up. It also means duplicating them here
would have created the collision the rulings exist to prevent.

## Recommendations

Three items surfaced by these rulings need an owner and are carried as named plan
steps rather than left in an out-of-scope note, which is where each would
otherwise rot.

The bucket manifest is a fourth persisted format read with no version gate of any
kind — not a ceiling, not a floor — so a manifest written by a newer application
is accepted silently. It is stronger than the record that surfaced it, and under
the compatibility-lifecycle rule a format must enrol its floor, version and
upgrader registry at birth. This one never did. It needs its own decision record
under the durability framing.

The bucket-event payload cap has now produced four instances of one shape and
three have been closed by hand, each rediscovered independently by a different
pass. Whether the substrate deserves a standing guard against joining a
variable-length value into a capped slot is the last systemic item. The figure
itself is an inline literal that no record ratifies, so a guard would also give it
its first declared home.

The sequence corpus stops exactly where the refusals live — 106 of 281 committed
contracts execute nothing, and the local filing finish line is display-only —
which is the structural reason the evidence dead end shipped undetected. The 72
directly-runnable frames are the cheap half and should be converted first, weighted
to the export and filing verbs, with the genuinely blocked frames recording why
they cannot execute so display-only becomes a stated constraint rather than an
unexamined default.

One methodological point is worth carrying forward, because it changed two of the
three rulings. Both S02's open-item list and S01's premise were accurate when
written and false when read. In this worktree a record's *facts* survive but its
*conclusions* expire, so a ruling must recompute the conclusion against HEAD
rather than inherit it — and it must date the commits it attributes work to,
since a shared feature tag is not evidence of a shared subject.
