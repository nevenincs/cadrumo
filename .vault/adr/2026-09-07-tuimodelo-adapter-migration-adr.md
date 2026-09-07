---
tags:
  - '#adr'
  - '#tuimodelo'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:b09e7376792207f7967f69347d31520cb52e5d81dad1475018b46cc692ed0a1c'
related:
  - "[[2026-09-07-tuimodelo-reference]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-09-07-tuimodelo-filing-lifecycle-adr]]"
  - "[[2026-09-07-tuimodelo-export-destinations-adr]]"
  - "[[2026-09-07-tuimodelo-satellite-families-adr]]"
---

# `tuimodelo` adr: `adapter to backend migration boundary` | (**status:** `accepted`)

## Problem Statement

Three decisions in this cluster name an adapter-to-backend migration as their prerequisite, and
none of them decides what it is. That gap is not cosmetic: a verification pass found that twenty
of the migration wave's twenty-four steps trace to no decision at all, resting instead on a
single aggregate paragraph of grounding with no per-item inventory and no stated boundary.

The migration is also larger and differently shaped than the surfaces that depend on it assume.
There are 159 identified violations of the adapter boundary across 224 command-line modules,
divided by lane as 62 ledger, 52 configuration and profile, 26 live and overview, 18 modelo and 1
cross-lane, of which 71 block a frontend surface (`2026-09-07-tuimodelo-reference`). No decision
says which of those this campaign owns, and an earlier reading of the evidence produced a false
premise that put an authorization change at the head of the wave when the frontend already
authorizes correctly.

The boundary itself is also undefined in practice. The standing architecture rule says adapters
may own transport grammar, confirmation, localization, redaction and error mapping, and nothing
else. It does not say how to classify a payload builder that derives a fact, a handler that
instantiates a repository, or a command specification that carries a default. Those three shapes
are most of the inventory.

A decision is needed before the migration wave executes, because without it every step is a
judgement call made twice and the wave has no closure condition anyone can evaluate.

## Considerations

- The violations are classification and routing rather than computation: only 7 of 224 modules
  touch decimal arithmetic (`2026-09-07-tuimodelo-reference`).
- Direct adapter imports appear in 46 modules over 122 lines, repositories are instantiated in 43
  handler sites, and repositories are injected into application functions at 68 call sites
  (`2026-09-07-tuimodelo-reference`).
- The migration target already exists in the tree: an application service that takes each
  repository as an optional parameter and defaults it, so a caller with nothing to inject simply
  calls it (`2026-09-07-tuimodelo-reference`).
- A reference handler shape also exists: build a typed request, call a composed service, map its
  errors to refusals, do nothing else (`2026-09-07-tuimodelo-reference`).
- The duplication is already real rather than prospective. The frontend composition root
  duplicates a command-line composition of the same use case and carries its own direct
  persistence imports, so a migration that binds only one adapter leaves the divergence standing
  (`2026-09-07-tuimodelo-reference`).
- Session authorization is not the blocker an earlier reading suggested: the frontend authorizes
  a session and admits per surface without any verb path. What is stranded is the capability
  declaration, which sits inside the command-line package that an import contract forbids the
  frontend from reaching (`2026-09-07-tuimodelo-reference`).
- Two migrations move filing-grade law rather than mechanism, and one of them currently carries
  no authority citation anywhere (`2026-09-07-tuimodelo-reference`).
- The ledger lane's 62 violations were inherited from a campaign that has since been archived, so
  they are already orphaned work rather than work belonging to an active owner
  (`2026-09-07-tuimodelo-reference`).

## Considered options

1. **Migrate all 159 violations in this campaign.** Rejected: it triples the wave, pulls in two
   other features' lanes, and delays every modelo surface behind work the modelo interface never
   touches.
2. **Migrate only what a modelo surface calls at runtime.** Rejected: it leaves the frontend's own
   duplicated composition in place, which is the divergence most likely to produce two different
   answers to the same question.
3. **Define the boundary, take the modelo lane plus the shared and frontend-side violations, and
   charter the residual explicitly.** Chosen: it is deliverable, it removes the duplication that
   already exists, and it makes the residual an owned campaign rather than an unstated remainder.

## Constraints

- This campaign does not make the command line a pure consumer overall, and no record in this
  cluster may claim that it does. Of the 159 identified violations only 19 sit in the lanes this
  campaign chartered as its own, so the residual at the migration wave's close is 140 less the
  named cross-lane rows taken here. The figure is derived, never rounded, and the two groups that
  sit outside the 159 entirely — the shared capability declaration and the frontend's own
  duplicated composition — are additional work rather than a deduction from it.
- The residual must be chartered as a named campaign at the start of this one, not recorded at the
  end. Deferring the charter to a final step repeats, at campaign scale, the orphaning this
  campaign's first wave exists to repair at row scale.
- A relocation that moves a filing-grade rule requires its governing provision cited before the
  move, under the calculation-grounding rule. A rule with no citable authority is not relocated.
- The frontend is bound by the same boundary as the command line. A migration that leaves the
  frontend composing persistence has not been performed.
- Relocations are atomic across definition, consumers, dynamic references and tests, under the
  architecture-boundaries rule. No transitional shim is created.
- The boundary must be enforced by a detector that fails when policy returns to an adapter, not by
  review alone.

## Implementation

The boundary is stated positively and by shape rather than by enumeration, so that a case not in
the inventory can still be classified.

An adapter may parse and validate input, confirm intent, localize, redact, project a typed result
into a transport form, and map application errors onto interface outcomes. It may not instantiate
a repository, decide eligibility, choose a default that affects a stored or filed value, classify
a domain value, order or filter a domain collection by a rule the domain owns, or hold a legal
condition. A payload builder projects; the moment it derives a fact, it has become policy. A
command specification declares transport; the moment it carries a value the application would
otherwise choose, it has become policy.

This campaign takes four groups, and the fourth is named because an earlier reading of this
decision omitted it and left a whole phase unchartered. The modelo lane, being the eighteen violations in the surfaces
the interface renders. The shared capability declaration, which both adapters need and only one
can currently reach. The frontend-side violations, being its duplicated composition and its
own direct persistence imports, because a boundary that binds one adapter and not the other is
not a boundary. And a small set of correctness divergences that cross lane lines - a coerced
zero, a hardcoded availability, a period-token rule - which are taken here rather than deferred
because each of them is reachable from a modelo surface and would otherwise produce two different
answers to one question.

The arithmetic is stated rather than approximated, because an approximate residual is how work
goes missing. There are 159 identified violations. This campaign takes the eighteen modelo-lane
rows, the shared capability declaration, the frontend-side duplication, and the named
cross-lane correctness rows. Everything else is residual, and the residual is what the count in
the chartering step must equal after the crossings above are subtracted, not a round number.

The residual — the ledger, configuration and live lanes — is chartered as a sibling campaign at
the start of this one, with the note that the ledger portion was orphaned by an archived
predecessor and is therefore unowned rather than merely deferred.

Each migration follows the shape already in the tree: the application service accepts its
repositories as optional parameters and defaults them, so that neither adapter composes
persistence, and the handler reduces to a typed request, a service call and an error mapping.

A detector accompanies the wave and fails when policy moves back into an adapter. Its absence is
what would let a half-migrated wave present as complete.

## Rationale

Defining the boundary by shape rather than by list is what makes the wave executable. The
inventory is evidence, not a specification; an implementer meeting a payload builder that derives
a fact needs a rule, and "it was not on the list" is not one.

Taking the frontend's violations alongside the command line's is the part most likely to be
questioned as scope creep, and it is the part that most needs doing. The duplicated composition is
not a latent risk, it is a live divergence: two adapters compose the same three repositories for
the same use case today, and correcting one of them makes the divergence worse rather than better.

Chartering the residual at the start rather than the end is a small ordering change with a
specific purpose. An unstated remainder becomes invisible; a remainder chartered in the final step
of the final wave is invisible for the entire campaign. Naming it first, with its counts and with
the fact that most of it is already orphaned, is the difference between a scope boundary and a
silence.

Refusing to relocate an uncited legal rule is not caution for its own sake. Moving a filing-grade
condition without its provision severs the only link between the code and the law it implements,
and the calculation-grounding rule exists precisely because that link cannot be reconstructed
later from the code alone.

## Consequences

The migration wave gains a decision it can be measured against, and its twenty untraceable steps
gain an authority. The closure condition becomes evaluable: no modelo handler instantiates a
repository or declares policy, both adapters call one service, and the detector passes.

The campaign accepts an explicit and stated incompleteness. The command line is a pure consumer of
the modelo lane and of nothing else when this campaign closes, and every record that touches the
subject must say so in those terms rather than the broader ones.

A sibling campaign is created early and must find an owner. That is a real coordination cost, and
the alternative is worse: a residual of 140 less the crossing rows taken here, most of it already orphaned once, left with
no home at all.

One relocation may be blocked on evidence rather than on effort. If the intracommunity rule's
provision cannot be established, the rule stays where it is and the surfaces that depend on it
inherit that limitation visibly, which is the correct outcome and not a workaround.

Binding the frontend to the same boundary enlarges this wave and touches a composition root
another campaign also edits, so it needs the single-writer coordination the plan already requires
for that file.
