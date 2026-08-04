---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:3a46c44db1a102a82ee7047da0b58c9c94b41e2fdc0b489cb9c8e987541e31e2'
step_id: 'S04'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Add a domain helper answering whether a path is derived, as the single written-once judgment over the declared patterns

## Scope

- `src/cadrumo/domain/user_profile/_schema.py`

## Description

## Outcome

The derived-path helper ships as a single written-once judgment, and the coordinator
executed the remainder of this phase directly after the whole agent fleet hit capacity
limits mid-flight.

The helper answers whether a path is engine-derived by matching it against the declared
pattern namespace, and returns the matching definition rather than a bare boolean so a
caller can name the surface that edits the real source facts without re-scanning. Both
consumers -- the registry contract validator and the write-door refusal -- ask through it,
so the two cannot disagree about what derived means.

It is deliberately NOT routed through the value-refusal authority, and the reason is
recorded at the declaration site rather than left to discipline. That authority judges
whether a VALUE may be stored at a declared field: it is value-scoped, expressly declines
to judge absence, and after the per-year declarations are deleted there is no declaration
left for it to judge against. This judgment is path-scoped, refuses every value including a
clear, and must keep answering once those declarations are gone. The two live in one module
because both are schema-level judgments, not because they are the same judgment.

That placement was adjudicated rather than assumed. A semantic sweep for an existing
canonical home surfaced the value-refusal authority as the near-miss, and the design
authority ruled beside-not-inside on three grounds: the signature cannot even be called for
a derived path once the declarations go, the contract is value-scoped where this is
path-scoped, and the existing path-legitimacy judgment already lives beside it rather than
inside it. Two consumers of that authority's kind enum branch exhaustively with deliberate
no-fallback arms, one pinned by a test, and all of it is untouched.

A later canonical-home sweep, run under the operator's reinforced discovery directive,
returned a clean negative across five probes by meaning: nothing pre-existing classified path
ownership, and the one promising candidate turned out to classify CLI commands for risk
annotation, a different domain entirely. Symbol confirmation found no derived, computed or
read-only axis anywhere in either package.

That sweep also caught its own contamination. The first probes ranked the executor's own
uncommitted code first, and it re-ran them with its own file excluded rather than reporting a
hit it had just written. A semantic index that has already absorbed your working tree will
confirm whatever you are about to declare.

Acting on the no-second-entry-point instruction, the executor went further than the Step
required and REMOVED a method it had itself added in the previous phase, because it was a
second way to ask the same question, pointing the registry validator at the canonical function
instead. Zero callers of the removed method remain. That is the directive applied against the
executor's own prior work, which is the harder direction.

## Notes
