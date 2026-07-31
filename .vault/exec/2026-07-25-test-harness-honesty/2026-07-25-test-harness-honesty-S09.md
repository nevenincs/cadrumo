---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:b0e4d48360f0cd92ba0e90d7714fcc48e0bdd07adbb13f2bf071e1ec575c6f5d'
step_id: 'S09'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
---

# Triage the empty-assert functions the screen flags

## Scope

- `dev/audit/vacuity_screen.py`
- `dev/audit/tests/`

## Description

- Re-run the screen and read every flagged function rather than trusting the count.
- Classify each as genuine vacuity, legitimate absence assertion, or paired detector control.
- Correct the screen where the classification showed it was wrong about a whole class.
- Add the screen's first test suite, including a regression for the defect introduced while fixing it.

## Outcome

The worklist was 22, and the triage found the largest class was not vacuity at
all. Fourteen entries were paired detector controls: a function asserting
`detector(planted) == ["a.b"]` beside `detector(clean) == []` was flagged because
the screen read the second assertion and could not see that the first proved the
code ran. That inverted the screen's purpose on precisely the tests that most
prevent the defect it hunts, and a worklist that is two-thirds noise stops being
read.

Equality against a non-empty literal is now recognised, function-scoped. The
worklist is 19 and every remaining entry is either a genuine unguarded corpus
scan or a legitimate absence assertion.

A second defect was found in the screen while testing the first fix: `assert x
== set()` was invisible to it. The reader matched literal collections, and an
empty set has no literal spelling in Python, so the blind spot was structural
rather than an omission. Now handled for the five empty constructors, with a
negative control proving a populated constructor call is not read as emptiness.

The screen also had no test at all. It shipped as a worklist people read and
acted on while nothing established that it distinguished the shape it claims
from its opposite -- the same unproven-instrument condition it exists to find.
Twelve cases now drive the real screen over synthetic trees at an injectable
root.

## Notes

The obvious fix for the first defect is wrong, and the record matters more than
the fix. Teaching `proves_it_scanned` to accept non-empty equality removes the
fourteen false positives and, in the same edit, silently WEAKENS the screen: that
predicate governs the module-level exemption, so a control running on a planted
dictionary begins vouching for every sibling gate in its file. It suppressed a
real finding in the locale-honesty module, whose controls use planted
dictionaries while its siblings walk four shipped catalogues.

Proving a detector works says nothing about whether the corpus it is pointed at
exists. The two signals are now separate predicates, and the regression is pinned
by a test verified to fail when the conflation is reintroduced -- checked by
reintroducing it, not by reading the code.

The screen lives in a directory that no test lane collected until this campaign's
sibling step opened one, so no test would have run had one existed. Its two
defects and its absent suite are all downstream of that same invisibility.

The stub-drift gate this step names as its starting point is SOUND and needs no
change. It is absent from the worklist, and the absence is for the right reason:
its conformance test asserts the scaffold wrote a non-zero number of stubs before
asserting the drift lists are clean, so it does prove the manager saw a module,
and its three detection tests assert positive membership in the missing, orphan,
and stale lists. This was confirmed by reading the assertions, not by observing
that the screen stopped naming it -- an absence from a worklist is exactly the
kind of clean negative that proves nothing on its own.

Remaining on the worklist: 19 entries, none yet actioned. They are real triage
output rather than noise now, which was this step's purpose, but the per-gate
work of adding a non-emptiness proof to each genuine corpus scan is not done.
Several are legitimate absence assertions needing no change; the module-level
exemption already covers some corpora guarded by a sibling.

Semantic code discovery was unusable throughout; the index answered confidently
from a truncated corpus, so every claim rests on direct reads and executed
measurement.
