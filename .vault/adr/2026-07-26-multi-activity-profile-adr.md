---
tags:
  - '#adr'
  - '#multi-activity-profile'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-05-27-multi-row-modelo-declaration-adr]]"
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace multi-activity-profile with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     Amend vs supersede: refinements and concretization rewrite the accepted
     record's body in place (modified: carries the revision); a new ADR with
     supersession is only for a major pivot. One accepted record per
     decision.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `multi-activity-profile` adr: `Multi-activity profile rows: generalise the shipped indexed-reader bridge and add the missing writer` | (**status:** `proposed`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

## Problem Statement

A taxpayer running two economic activities cannot be represented. The profile
schema declares the activities section repeatable, and no surface writes, reads
or models more than one row of it.

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

Semantic code discovery is unavailable at the time of writing - the code index is
truncated while the vault index is healthy, and the two fail independently. Any
implementation must substitute an exhaustive targeted search over the bounded
surface and say so, rather than reporting that discovery came back clean.

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

A **field-set reconciliation** deciding, for each field the AEAT row carries and
the profile row lacks and vice versa, whether it is added, mapped or deliberately
absent. Indexing without this makes the section countable but still unable to
express what the form records.

The new reader derives its required-field set from the schema rather than
restating it. The reference records that the shipped resolver restates it and has
already drifted by one field; that drift is a defect to reconcile in passing, not
a pattern to copy.

## Rationale

The knockout is that the pattern is already accepted and in production for a
sibling section, per the reference. A second mechanism for the same question
would have to justify not only itself but the divergence, and nothing in the
evidence distinguishes activities from the section already served.

The alternative with real support - stripping the flag - fails on the diseño: a
form-layout artefact and a legal text, produced by different processes, agree
that the fact is plural. That agreement is what makes this a decision about
implementation rather than about modelling.

Choosing to derive rather than restate the required set is the campaign's own
finding applied forward: a declaration that nothing enforces, and an enforcement
that restates a declaration, are the same defect seen from two sides.

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
