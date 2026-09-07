---
tags:
  - '#adr'
  - '#tuimodelo'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:3671144a1c8a81ea4a319caca7b869f4b0f21dfd6f444ba61ac47572da385605'
related:
  - "[[2026-09-07-tuimodelo-reference]]"
  - "[[2026-08-24-tui-modelo-workspace-interface-adr]]"
  - "[[2026-09-07-tuimodelo-export-destinations-adr]]"
---

# `tuimodelo` adr: `satellite command family dispositions` | (**status:** `proposed`)

## Problem Statement

The modelo action denominator classifies 79 candidates. The campaign's other decisions govern
the core loop — create, calculate, edit, verify, reconcile, file, export — which leaves roughly
half the denominator addressed by nothing. Those remaining families are not fringe: they
include the entire cryptographic review exchange, the census logbook, the withholding
communication, the IVA carry-forward wallet, the evidence-bundle audit, the spreadsheet round
trip, and the registry-inspection reads.

Leaving them undecided has a specific failure mode rather than a vague one. A plan can only
schedule what a decision governs, so an ungoverned family is silently dropped, and the
denominator cannot catch that because a row sitting at its original pending disposition looks
identical to a row nobody considered. Two of these families also turn out to sit inside the
core loop rather than beside it, so "satellite" is partly a misnomer this record has to correct
(`2026-09-07-tuimodelo-reference`).

A decision is needed before the plan is authored, because the plan's wave structure depends on
knowing which of these need a surface, which fold into a surface already decided, and which are
honestly command-line work.

## Considerations

- Only seven modelo operations are registered, and the frontend dispatch table is keyed to the
  same seven. Every mutation in these families writes outside the supervisor, with no journal,
  lease or cancellation (`2026-09-07-tuimodelo-reference`).
- The IVA wallet gate blocks modelo 303 calculation, verification, filing and export pending an
  explicit taxpayer override, and the override verb is the only remedy
  (`2026-09-07-tuimodelo-reference`).
- The aggregate verb is not a read. It is the sole operator write path for retención and
  percepción observations feeding calculation bindings for modelos 111, 115, 123 and 190, with
  replace-the-set semantics (`2026-09-07-tuimodelo-reference`).
- The review-package exchange cannot be completed with the verbs that ship: the function that
  publishes a recipient's encryption key has no caller anywhere, so a recipient cannot obtain
  the key material the address-book command requires. There is also no package catalogue; every
  verb takes an operator-supplied path (`2026-09-07-tuimodelo-reference`).
- Two review-package rows declare no write route while carrying local-state side effects and
  emitting bucket events. The denominator's drift check compares against the spec's own
  declaration, so an under-declaring spec is invisible to it
  (`2026-09-07-tuimodelo-reference`).
- The evidence-bundle service has zero production callers and nothing writes its namespace, so
  all three audit verbs require an identifier an operator cannot obtain
  (`2026-09-07-tuimodelo-reference`).
- The spreadsheet family has no application service; its logic is command-resident, and its
  staleness rule is a multi-field metadata match that already refuses structurally
  (`2026-09-07-tuimodelo-reference`).
- The census family is a local logbook of declarations already filed at the authority's site,
  with an alta-first and baja-terminal sequence guard
  (`2026-09-07-tuimodelo-reference`).
- The withholding communication is delivered to an employer rather than to the authority, and
  its lifecycle has two distinct marks (`2026-09-07-tuimodelo-reference`).
- A schema facet already exists on the workspace model, and an overview readiness panel is
  already part of the decided surface set, so several inspection reads have an existing home
  (`2026-09-07-tuimodelo-reference`).

## Considered options

1. **Give every family its own destination.** Rejected: it would roughly double the destination
   catalogue for families that differ enormously in operator value, and several of them cannot
   be completed at all with what ships.
2. **Defer every family until the core loop is delivered.** Rejected: two of them are inside the
   core loop. Deferring the wallet leaves a reachable dead end in modelo 303, and deferring
   aggregate leaves four modelos with no way to enter their calculation inputs.
3. **Fold everything into existing surfaces.** Rejected: the cryptographic exchange and the
   withholding communication have real multi-step lifecycles that a panel cannot carry.
4. **A disposition per family, chosen on operator value and completability.** Chosen: it treats
   the families as what they are — a heterogeneous set — and records a reason and a reopening
   condition for each, so a deferral is a decision rather than an omission.

## Constraints

- Two families are reclassified out of "satellite" and into the core loop; the plan must
  schedule them with the core waves, not after them.
- No family may be surfaced before its operations are registered. Registration is a
  prerequisite for all of them, and it is a larger prerequisite than it appears because none
  exists today.
- The review-package exchange must not be surfaced before its key-publication defect is fixed;
  a surface over an incompletable workflow is worse than none.
- The audit family must not be surfaced while its identifier is unobtainable.
- Under-declared write routes must be corrected in the specs themselves. Correcting them only in
  the classification table would leave the gate blind to the same class of error.
- The spreadsheet family's command-resident logic must move to an application service before any
  surface claims it, under the adapter migration this campaign already requires.
- A deferral in this record carries a named reopening condition. A deferral without one is the
  omission this record exists to prevent.

## Implementation

Four families become first-class surfaces. The IVA wallet gains a balance view and all three of
its write paths - seed, correct and override - because a family of four rows is not disposed of
by surfacing one of them, and an operator who can override but not correct is left with the
blunter instrument. The override is presented from within the modelo 303 workspace where the gate actually blocks, because
an override offered anywhere else asks the operator to leave the problem to solve it. Aggregate
becomes a proper observation-entry surface for the four withholding modelos, replacing
command-line JSON with a typed editor over the same replace-the-set semantics. The withholding
communication gains a small lifecycle surface plus the listing verb it is missing. The review
exchange gains a package catalogue and a guided sequence, but only after its key publication is
fixed.

Seven capabilities fold into surfaces already decided. The census logbook becomes a panel on the
taxpayer profile, where its subject already lives, and it carries its three write paths rather
than reading only: alta, modificacion and baja are what make it a logbook, and the alta-first,
baja-terminal sequence guard is the family's defining behaviour. Its parser refuses
unconditionally today, so the panel declares itself unavailable with that reason until the
parser is fixed rather than presenting an surface that can never be populated. The describe, casillas, casilla
and formulas reads fold into the schema facet the workspace model already carries. Requires and
readiness fold into the overview readiness panel. The modelo listing folds into the work-unit
picker.

Five stay command-line only, with the reason recorded. The four spreadsheet verbs stay because
the operator's actual working surface is the browser, the round trip is authenticated
externally, and its staleness rule already refuses structurally rather than relying on
presentation. The support matrix stays because it is a maintainer's coverage grid; the
operator-facing form of that question is already answered by the work-unit listing.

Two defer with conditions. Projection and comparison defer until a planning surface is
chartered, because they answer a forecasting question this campaign does not otherwise address.
The audit family defers until the first production caller of the evidence-bundle service lands,
which is the precise condition that makes its identifier obtainable.

Every family in this record, whatever its disposition, keeps its row in the denominator and
carries its disposition, reason and reopening condition there. That is what makes a deferral
auditable rather than a silence.

## Rationale

The decision turns on separating three questions that look like one: does the operator need
this, can it be completed with what ships, and does it belong inside the core loop. Answering
them per family produces a different answer than any uniform policy would, which is itself the
argument against the uniform options.

The two reclassifications are the most consequential part of the record and were the least
obvious. The wallet reads as a peripheral ledger feature until one notices that its gate stops
the most-used modelo in the product from being filed at all, and that the only remedy is a verb
with no surface. Aggregate reads as one more registry-inspection verb until one notices it is a
destructive write path for calculation inputs; being a single verb among ten reads is exactly
what hid it. Both were missed by an earlier pass of this campaign, which is evidence for
enumerating dispositions explicitly rather than trusting a family's apparent size.

Refusing to surface the review exchange and the audit family until their blocking defects are
fixed is the same principle the campaign applies elsewhere: a control that cannot complete its
own workflow is not a feature. Recording the precise reopening condition — a caller for the
bundle service, a publication path for the recipient key — turns both from vague backlog into
scheduled work.

Keeping the spreadsheet family on the command line is the one disposition most likely to be
challenged. It is defensible because the sheet itself is the operator's working surface, so a
full-screen wrapper would add a step rather than remove one, and because the staleness contract
is enforced structurally rather than by anything a surface would show.

## Consequences

The plan can now schedule every denominator row, and a dropped family becomes visible as a row
without a disposition rather than as an absence nobody notices.

Two waves get heavier than the earlier shape suggested. The wallet and aggregate move into the
core loop, and both need operation registration before they can be surfaced, which is work the
campaign had not costed.

Operation registration is revealed as a much larger prerequisite than the core loop alone
implied: none of these families has a registered operation, so bringing them under supervision
is a substantial body of backend work that gates every surface in this record.

Fixing the under-declared write routes improves the denominator for everyone, because the same
class of error can hide anywhere in the table. It also means the gate this campaign is
strengthening will red on rows nobody has looked at yet, which is a good outcome that will
initially look like a regression.

Two families ship no surface at all, and two more stay deferred. That is a narrower product
than the brief implied, and the honest reading is that some of these capabilities are not yet
finished enough to present — which the reopening conditions now say out loud.
