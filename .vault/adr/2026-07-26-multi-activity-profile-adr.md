---
tags:
  - '#adr'
  - '#multi-activity-profile'
date: '2026-07-26'
modified: '2026-07-30'
body_hash: 'sha256:3676277469724331ae26ace2fb23163cfc61d6a91634ef10d9d848131e16cc29'
related:
  - "[[2026-05-27-multi-row-modelo-declaration-adr]]"
  - "[[2026-07-25-censal-profile-autofill-plan]]"
  - '[[2026-07-26-multi-activity-profile-reference]]'
---

# `multi-activity-profile` adr: `Multi-activity profile rows: generalise the shipped indexed-reader bridge and add the missing writer` | (**status:** `proposed`)

## Problem Statement

A taxpayer running two economic activities cannot be represented. The profile
schema declares the activities section repeatable, and no surface writes, reads
or models more than one row of it.

**This is not bigger in scope than it first reads - it is differently shaped:
less to invent, more to reconcile.** The read half of the pattern already ships
for a sibling section under an accepted decision, so the work is a migration
with a missing writer rather than a design job. That difference decides who
should do it and in what order, and it is the reason the migration ruling below
is a precondition rather than a verification step.

The decision is needed now because the declaration and the implementation have
already been mistaken for each other twice. The flag was nearly stripped as
incorrect before the AEAT diseño settled the cardinality, and a separate gate was
built and discarded on the assumption that a required row-field reaches a
taxpayer. Both are recorded in
`2026-07-26-censal-profile-autofill-campaign-close-honesty-review-audit`. Leaving
the section declared-but-unimplemented invites the same confusion a third time,
and the next arrival is likelier to resolve it by weakening the declaration than
by supplying the implementation.

## Considerations

The cardinality is authoritative and bounded, not a guess about future need -
two artefacts of different kinds agree, per the close-review audit.

The read half of this capability already ships for a different section, as a
complete profile-to-modelo bridge under an accepted decision, per
`2026-07-26-multi-activity-profile-reference`. This is a second instance, not a
new mechanism.

No writer exists for any repeatable section, so the gap is symmetric rather than
specific to activities (same reference).

The nine flat production sites fail silently rather than loudly when handed an
indexed path, because an unmatched key reads as undeclared (close-review audit).
That makes a partial migration more dangerous than either end state.

One modelo genuinely wants a single principal activity, which is a projection
over the rows and not evidence against holding several (close-review audit).

The section's own field set does not match the AEAT row's, so indexing alone
does not make the profile able to express what the form records (same audit).

## Considered options

**Strip the repeatable declaration and model one activity.** Rejected: the
diseño evidence shows the underlying fact is plural and bounded at four, so this
encodes a known-wrong model to match a temporarily-thin implementation.

**Generalise the shipped indexed-reader pattern to activities, and add the
missing writer.** Chosen.

**Invent a fresh row mechanism for profile sections.** Rejected: it would place
a second answer beside an accepted one for the same question, which is the shape
this campaign spent its length removing.

**Follow the one indexed writer that ships.** Rejected on inspection - its rows
live outside the schema's declaration, per the reference. It is the wrong shape
to generalise even though it works.

**Defer until a taxpayer needs it.** Rejected: the cost is not deferred, it is
transferred. Every surface added meanwhile is another flat lookup to migrate.

## Constraints

The parent decision (`2026-05-27-multi-row-modelo-declaration-adr`) is accepted
and in production, and this record depends on its row-model layer rather than
extending it. Nothing here requires reopening it.

Three grounding items are unverified and are named in the close-review audit as
must-not-inherit-as-done: the empirical surface sweep, the two-activity módulos
calculation, and two questions about the other renta modelo's shape and whether
any módulos unit slot is shared across activities. The last of these can change
the shape of a per-activity model rather than only its necessity, so it belongs
before design rather than after.

Semantic discovery was not relied on at the time of writing. The two indexes fail
independently and must be checked separately, and **no state field is evidence
either way** - one index reported a terminal successful state at a section count
far below the tree's size, while the other reported `running` and nonetheless
answered correctly under a two-probe check. Neither `succeeded` nor `running`
tells you anything; only a probe does. This record was authored without a usable
code index. It is
therefore authored from evidence already in the vault and from targeted search,
not from fresh semantic discovery, and an implementation must substitute an
exhaustive search over the bounded surface and say so rather than reporting that
discovery came back clean.

One consequence of that is worth stating rather than leaving implicit: this
record cannot rule out that some part of this capability already exists under a
name nobody searched. That has happened twice in the parent campaign, and the
reference's finding - that the read half already ships - is itself an instance
found only by reading an adjacent accepted decision rather than by searching.

## Implementation

Four layers, and the order matters because the middle two are the dangerous ones.

A **writer** for indexed rows in a repeatable section, expressed in terms of the
schema's declaration rather than a path convention. This is the piece that exists
nowhere and it is what makes the section reachable at all.

**Index-aware reading** at the sites that currently address the section flat,
replacing exact-string lookups. This is the migration that must not be partial:
a site left flat does not fail, it silently reports the field undeclared, so the
work is only safe as a complete sweep with the empirical check that the sweep was
complete.

A **collection-valued downstream model**, replacing the single scalar the
deadlines profile carries today, plus a **principal-activity projection** for the
modelo that wants one. The projection is where the singular casilla is served,
and keeping it explicitly a projection is what stops the plural fact being
re-collapsed later.

**The profile row is decided here rather than deferred**, because indexing a row
whose shape is wrong only makes the wrong shape countable. Per field:

*Descripción* and *grupo o epígrafe* keep their existing profile fields and map to
the AEAT row directly. *Sección I.A.E.* is **added**: the reference records it
carried per activity slot throughout the diseño, and an epígrafe identifies an
activity only within its sección, so a row without it cannot address the activity
it claims to. *Tipo de actividad* is **added** on the same grounds - it is part of
the triple AEAT records per slot, not a derived classification.

*CNAE* is **retired from the row**. It has no AEAT counterpart, and the reference
measures it as having no reader and no writer anywhere in the tree. Carrying an
inert field into a new row model would give the row a fourth member that no
consumer can use and no form expects. Retiring a declared schema field is a
change to persisted shape, so it is called out as its own step rather than folded
into the row work.

A **principal-activity rule**, because the modelo asks which activity is
principal and that is a declaration rather than a lookup. The row carries an
explicit marker. Exactly one row is principal by construction when the section
holds one row; several rows with none marked **refuses** rather than selecting
by index or by amount. Choosing by position would make row order load-bearing
when nothing else in the section treats it that way, and choosing by amount
would invent a criterion the form does not state.

**A resolver enforces what its row model consumes; the schema declares what the
profile must hold; those are legitimately different sets.** The new reader
therefore derives its required set from the row it builds, and neither restates
the schema by hand nor inherits it wholesale.

This corrects an earlier version of this record, which ruled that the reader
should derive from the schema. That would have made a reader enforce fields the
modelo does not carry - a new defect introduced by the rule meant to prevent
one. The shipped resolver's set differing from the schema's turned out not to be
drift at all: the field it omits is one the form does not carry per member, so
the resolver enforces exactly what it consumes and is correct.

## Rationale

The knockout is that the pattern is already accepted and in production for a
sibling section, per the reference. A second mechanism for the same question
would have to justify not only itself but the divergence, and nothing in the
evidence distinguishes activities from the section already served.

The alternative with real support - stripping the flag - fails on the diseño: a
form-layout artefact and a legal text, produced by different processes, agree
that the fact is plural. That agreement is what makes this a decision about
implementation rather than about modelling.

The campaign's own finding applies forward, with its resolution corrected. A
declaration that nothing enforces, and an enforcement that restates a
declaration, are the same defect seen from two sides - **but the answer is not to
make them match. It is to ask of each set what question it answers.**

Measured in this section family, the two cases resolve in opposite directions. A
required field that feeds a readiness gate, a calendar check and seven operator
surfaces is a declaration that is right and an enforcement that is missing. A
required field the form does not carry per row and no code reads is a
declaration that is wrong. Making either "match" its counterpart would fix one
and break the other, which is why the rule has to be about the question rather
than the agreement.

## Consequences

The section becomes able to express what the taxpayer is and what the form
records, and the módulos precondition already noted in the registry gains the
inputs it names as its condition.

The migration is the risk, and it is a silent one. Nine sites that currently
answer confidently and wrongly when handed an indexed path will keep doing so
until each is converted, and no test currently fails to signal it - which is why
the empirical sweep is a precondition rather than a verification step.

A second reader deriving its required set from the schema will disagree with the
shipped one until that is reconciled, and the disagreement will surface as a row
being flagged incomplete by one path and not the other. Better surfaced than
inherited, but it is work this record creates rather than finds.

The principal-activity projection is a place where a later reader may reasonably
mistake the projection for the model, which is how this section reached its
current state. Naming it a projection in the code, not only here, is the cheap
defence.
