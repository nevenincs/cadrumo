---
tags:
  - '#reference'
  - '#unfalsifiable-test-sweep'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:f74e345c2297f331598640b692fb9cc25cc6135c70358148077b220c27ab1959'
related: []
---
# `unfalsifiable-test-sweep` reference: `Census of tests that cannot fail`

## Summary

Measurement of the tests in this repository that pass regardless of the code
they are meant to guard. The starting question was not "which tests look
tautological" but "which tests could not fail if the thing they check broke".

Two instruments already exist and are not in question. A hard-zero static gate
refuses syntactic tautologies (`assert True`, `assert x == x`, constant
comparisons) and is green. A screen reports gates that assert an empty result
with no proof they scanned anything, and deliberately over-reports.

The gap both leave open is the one measured here, and both name it themselves:
neither can tell a legitimate negative control from a detector that was never
proven capable of firing.

## The decisive criterion

A negative control - a test asserting a detector stays silent - is sound only
when a positive control proves the same detector can speak. Without one, the
pair collapses into a single unfalsifiable assertion, because a detector that
matches nothing at all satisfies the negative control perfectly.

The same criterion applies to a corpus: a scan asserting "no violations" over a
corpus that could be empty reports exactly what a clean tree reports.

## Measurement

The screen flags 169 empty-assert functions across 362 modules. Classifying
every test function in each flagged module by whether its assertions can only
confirm an absence:

**Of 96 modules carrying flagged functions, 92 contain at least one positive
control. Four do not.**

That is the useful reduction: the screen's own over-reporting is confirmed as
over-reporting, and the worklist that actually needs reading is four modules
rather than one hundred and sixty-nine.

The four are `dev/docs/tests/test_docs_build_full_scope.py`,
`dev/docs/tests/test_docs_build_localized.py`,
`src/cadrumo/tests/test_dev_dotenv_bridge.py` and
`src/cadrumo/tests/test_utf8_enrollment_inventory.py`.

## The finding that survived reading

`src/cadrumo/tests/test_utf8_enrollment_inventory.py` walks two corpora through
module-local accessors. Neither is floored anywhere in the repository: nothing
asserts either walk returns a single file.

The module carries three tests. Two scan for bare UTF-8 literals and raise only
when they find one. The third checks that no ratchet entry has gone inert.

Emptying both walkers at runtime leaves the ratchet-inert test failing and both
scan tests passing. So the production scan is not floored by design but by
accident: with 38 ratchet entries live, an empty corpus makes all 38 look
vanished and the third test fails loudly.

Emptying only the dev walker produces three passes. **The dev scan is
unfalsifiable today**, with nothing anywhere that would notice.

## Why the accidental floor is worse than none

The ratchet drains by design. Its own failure message instructs the reader to
delete entries, and its docstring records the backlog falling from 78 to 38.

So the production scan's only protection is strongest when the cleanup has
barely started and disappears at the moment it succeeds. A project that
finishes the work the ratchet exists to drive silently converts a working gate
into a permanently vacuous one, and no test fails at the moment it happens.

That is a sharper defect than a missing floor, because it is invisible in every
green run and arrives as a consequence of doing the right thing.

## Not defects

`test_dev_dotenv_bridge.py` returns early when no `env/.env` exists, so it
asserts nothing on CI or a fresh clone. The early return is documented at
length, including why `pytest.skip` is unavailable to it under the project's
skip-shortcut gate. It is a deliberate, recorded trade rather than an oversight.

The two docs-build modules assert a build produces no errors. Emptiness is the
property under test there, which is the screen's own first exemption.
