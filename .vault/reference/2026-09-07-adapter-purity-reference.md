---
tags:
  - '#reference'
  - '#adapter-purity'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:b6e11fc88c110fe78cf2ed024b71856067f1503c39b17e87e1437f477b31fe58'
related:
  - "[[2026-09-07-tuimodelo-adapter-migration-adr]]"
---

# `adapter-purity` reference: `the residual adapter-boundary violations and their ownership`

## Overview

This feature exists because a sibling campaign took a defined slice of the adapter-boundary
inventory and refused to leave the rest as an unstated remainder. The migration decision that
chartered it is explicit that the residual is named at the START of that campaign rather than
recorded at its end, on the ground that a remainder chartered in a final step is invisible for the
entire campaign.

Nothing here is scheduled yet. This record is the grounding a future campaign starts from: what
remains, how the figure is derived, who owned it before, and which parts have no owner at all.

## What remains

The command-line tree holds 159 identified adapter-boundary violations across 224 modules. By lane
the inventory divides as 18 modelo, 62 ledger, 52 configuration and profile, 26 live and overview,
and 1 unassigned cross-lane row. By severity it divides as 71 blocking a full-screen surface, 61
correctness, and 27 hygiene.

The modelo campaign takes 19 of those: the 18 modelo rows and the single cross-lane row. It
additionally takes a small number of named correctness rows that cross into other lanes, because
each is reachable from a modelo surface and would otherwise produce two different answers to one
question. Two of those named crossings fall outside the modelo lane, being a hardcoded availability
model on the overview evidence path and a ledger period-token applicability rule.

THE RESIDUAL IS THEREFORE 140 LESS THE CROSSINGS, AND THE EXACT FIGURE IS NOT ASSERTED HERE. The
lane arithmetic gives 140, being 62 plus 52 plus 26. The crossings are identified by the step that
takes them rather than by inventory row, and mapping a step to a row was not attempted, because
asserting a precise remainder from an unconfirmed mapping is the rounding the governing decision
forbids. The modelo campaign carries its own step to reconcile the take and the remainder against
the 159, and that reconciliation is the authority for the final number.

## Who owned it

The ledger lane's 62 rows are the largest block and the only one that is UNOWNED rather than
merely unscheduled. They were inherited from a campaign that has since been archived: its plan,
decision, reference and audits all sit under the archive, and the gate its holds waited on can
never close because the step that would close it is unchecked in an archived plan. Those rows have
therefore been orphaned once already.

That history is the reason this record exists rather than a note at the end of another plan. A
remainder with no named owner is indistinguishable from a remainder nobody considered, and this
block has already been through that once.

The configuration and profile lane and the live and overview lane have no comparable archived
predecessor; they are unscheduled rather than orphaned.

## The boundary to apply

The boundary is defined by shape rather than by enumeration, so a case absent from the inventory
can still be classified. An adapter may parse and validate input, confirm intent, localize,
redact, project a typed result into a transport form, and map application errors onto interface
outcomes. It may not instantiate a repository, decide eligibility, choose a default that affects a
stored or filed value, classify a domain value, order or filter a domain collection by a rule the
domain owns, or hold a legal condition.

Two shapes account for most of the inventory and are worth stating because they are the ones a
reader misclassifies. A payload builder projects; the moment it derives a fact it has become
policy. A command specification declares transport; the moment it carries a value the application
would otherwise choose, it has become policy.

## What the modelo campaign proved that applies here

The migration target already exists in the tree rather than needing invention: an application
service that accepts each repository as an optional parameter and defaults it, so a caller with
nothing to inject simply calls it, and a handler that reduces to a typed request, a service call
and an error mapping.

One relocation may be blocked on evidence rather than effort. A rule that moves filing-grade law
requires its governing provision cited before the move, and a rule with no citable authority is
not relocated.

A declaration change can silently bypass a guard. One row in the modelo slice declared no write
route while writing profile storage, and the root storage-write guard keys on that declaration
alone, so the write skipped the guard entirely. The same class of error is invisible to a drift
check, because the check compares against the specification's own declaration.
