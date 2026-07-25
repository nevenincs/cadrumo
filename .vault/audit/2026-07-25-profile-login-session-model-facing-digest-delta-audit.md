---
tags:
  - '#audit'
  - '#profile-login-session'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# `profile-login-session` audit: `model facing digest delta`

## Scope

The model-facing description digest and its re-pin, and the accounting recorded
in the pin commit's body. This document supersedes that accounting.

The digest was re-pinned to `64108a20` at count 1638, parented on the commit it
was measured over. The pinned VALUE is sound: two readers measured the same
digest, total and per-surface shape independently at different tips, the
description sources were content-clean, and the gate passes. The pin commit's
body nonetheless asserts that every unit of the count delta is accounted for.
That is true of one axis and false of the other, and the false half was
authorised on the strength of my own incomplete work.

## Findings

### The tool axis is fully attributed

Two tools were added and two removed by the login/logout cutover, and one tool
was added by the export-reconcile maintenance verb. Because the intermediate
reference reading was taken between the additions and the removals, the cutover
contributes minus two rather than zero across that window. Minus two plus one is
the minus one observed. This axis closes exactly.

### The argument axis has four unattributed units

The named terms sum to minus two against an observed plus two, leaving four
argument descriptions unexplained. No mechanism proposed by either reader
accounts for them:

- Schema-shape expansion does not exist. Every argument description is exactly
  one flat node under the schema's properties map, with no branch expansion and
  no nesting, so an optional path yields the same single node as a required one.
  Four extra nodes therefore require four more described options, not four more
  nodes from the same options.
- Net option and argument declarations across the non-test command tree are
  identical at both ends of the window. This does NOT by itself exclude four
  additional described options, because it is a NET count and cannot distinguish
  a compensating pair added in one place and removed in another. It is weaker
  evidence than I originally claimed.
- Locale help leaves net to zero across the window: one described option gained
  a help leaf and one lost it.

### The baseline-contamination hypothesis was raised and REFUTED

I proposed that the intermediate reference was itself measured over a dirty
tree, which would have made the four units an artefact of the reference rather
than a real surface change. The second reader tested it rather than accepting
it, and it does not hold. Of the six files dirty at that reading, one was an
untracked test module that can register no command, four contain no
description-bearing construct of any kind, and the fifth was tested directly:
all ninety-one of its description literals were harvested by syntax tree and
searched for in the live projection, and none appears. That reference is clean,
so the four units are a property of the surface.

The disposition is therefore UNATTRIBUTABLE rather than pending, and for a
stronger reason than uncertainty: the four units are real, and they cannot be
named because no identifier inventory was preserved at the reference point and
none can be produced without a checkout. A future reader should stop looking,
and should not doubt the units existed.

## Recommendations

Emit the per-owner argument map alongside the digest. Key it by OWNING ENTITY,
not by leading identifier segment: a tool argument owns as its tool, while a
prompt argument owns as its prompt, so splitting on the first separator
collapses every prompt argument under one meaningless bucket. That is not
hypothetical -- the first implementation did exactly this to sixty-eight
entries.

Prove the map with TWO assertions, not one. A sum-to-total test is necessary
and NOT sufficient: the same first implementation summed correctly while
decomposing nothing, passing the stated invariant and defeating the field's
whole purpose. The second assertion must be on key SHAPE, so a catch-all or
unapproved key surfaces as an anomaly. A check on a derived quantity's TOTAL
cannot validate its DECOMPOSITION; those are separate properties and each needs
its own assertion.

With the map correctly keyed and both assertions in place, the next delta names
its own owners by subtraction. This entire investigation behind a one-line
change existed only because the artefact preserved a total and not its
composition.

Three instrument lessons, each earned by being wrong:

A clean-looking positive is harder to catch than a clean-looking negative,
because it supplies its own satisfying story and closes the inquiry. Both of my
false attributions were plausible answers to "could this mechanism explain the
delta" -- one naming a door removed six days outside the window, one naming a
mechanism that does not exist. Neither survived enumeration. Do not ask whether
a candidate explains an observation; enumerate what changed and read it off.

A second reader who re-derives the measurement catches what a reader who checks
the reasoning cannot. The reasoning here was sound throughout; the premises were
false. Review of sound reasoning over false premises returns clean, and passing
it upward adds authority to the error rather than filtering it.

A directive that specifies the CONTENT of a factual record is only as good as
the fact was when it was issued. Procedural directives survive staleness;
substantive ones do not. Frame them as "record what you find" rather than
"record X", and treat any substantive directive received as a hypothesis to test
rather than content to transcribe.
