---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:41102b0253a7e97d0a5c269edf87316190dc75791931ffe2fbd4f7ead9bc95e2'
step_id: 'S10'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
---

# Extend the vacuity screen, and search for escapes that outlived their reasons

## Scope

- `dev/audit/vacuity_screen.py`
- `src/cadrumo/tests/`
- `dev/`

## Description

- Extend the screen past the single shape it detected.
- Sweep every exemption structure in both trees for entries whose target is gone.
- Attempt a detector for the total-where-the-property-is-a-decomposition shape.
- Record the negative result where a shape proved not reliably detectable.

## Outcome

Two of this step's three concerns are closed and the third has a measured
negative result.

The screen was extended twice. It now recognises a paired detector control
rather than flagging it, and it now sees a constructed empty: `assert x == set()`
was invisible because the reader matched literal collections, and an empty set
has no literal spelling in Python, so the blind spot was structural. Both changes
are covered by the screen's first test suite, and the module-exemption regression
introduced while making the first change is pinned by a case verified to fail
when the conflation is reintroduced.

The systematic escapes search ran and the corpus is almost clean. Across five
path-shaped exemption collections in code (35 entries), four JSON debt and
baseline registers (95 entries), and the pinned os_keychain node-id set (6
entries), exactly one entry was dead: `src/cadrumo/locales/scaffold.py`, exempted
from the coverage gate for a path `git log` shows never existed. It is removed,
a neighbouring comment that misdescribed where `locales/__main__` dispatches is
corrected, and that gate now carries a liveness guard proven by reintroducing the
stale entry.

The third shape, a gate asserting a TOTAL where the property is a DECOMPOSITION,
was attempted and abandoned on evidence. A detector for "asserts `len(X) == N`
and never asserts membership" returned 13 candidates across 234 modules. Two were
read in full and both were false positives: one asserts surviving scores and
merged record ids that the AST check could not recognise as membership, and in
the other the count IS the property under test, since two distinct inputs must
not collapse. Shipping that detector would have produced the mostly-noise
worklist this step exists to prevent.

## Notes

The negative result is the part worth keeping. Membership assertions take too
many forms for a count-shaped AST check to recognise: attribute comparisons,
indexed access, derived sets, and helpers that assert inside a call. A detector
that cannot see them reports every rigorous test as a suspect, which is the
precise failure this campaign already corrected once when the screen flagged
fourteen paired controls as vacuity.

That correction is why this was measured rather than assumed. The same mistake
made twice in one campaign would have been avoidable by reading two flagged
functions, which is exactly what settled it here.

Three probes written during the escapes sweep were themselves wrong before they
were right, and each was caught by an internal contradiction rather than by
review. One resolved exemption paths against the repository root when they are
package-relative, and reported ten dead entries in the very module whose own
liveness guard passes -- the contradiction that exposed it. Another matched
collection names by keyword and reached no collection holding a dotted or node-id
entry, returning a clean zero that proved only that the filter missed. A clean
negative from an instrument nobody has proven is worth nothing, which is this
campaign's own thesis applied to its own tooling.

Semantic code discovery remained unusable throughout; every claim rests on direct
reads and executed measurement.

## Correction, same day

The worklist figure above understated the finding, and the record is corrected
rather than left standing. A peer tightened the module-level exemption to require
SAME-CORPUS proof, on the same reasoning this step applied one level down: a
sibling asserting one substrate is populated vouches for a scan over that
substrate, not over a corpus it never touched. Crediting it module-wide silenced
110 functions tree-wide.

The worklist is 123, not 19. Of those, 104 were newly exposed by that tightening
and 19 are the set this step measured. So "every remaining entry is a genuine
scan or a legitimate absence assertion" was a claim about a screen that was
itself still laundering, and the honest number was always higher.

The reflex on seeing 123 was that the instrument had regressed to noise, which is
the objection this step raised when the screen flagged fourteen paired controls.
That reflex was checked rather than acted on, and it was wrong. Two newly-exposed
entries were read in full and both are real: one iterates a helper call and
asserts the result empty, so the entire marker gate would pass vacuously if that
helper ever returned nothing; the other reads a fixture attribute with the same
exposure. Reaching a corpus through a call rather than a bare name is exactly the
case the tightened credit refuses, and refusing it is correct.

The lesson is narrower than "the screen was wrong again". Both times the screen's
own exemption logic was the defect, and both times it was found by someone
distrusting a number rather than the code. A count that moves by 5x is a prompt
to read two entries, not to conclude anything.
