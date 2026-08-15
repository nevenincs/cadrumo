---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:20c8e59e9c229e73c58e0f0e6163c141c6f064646a9af42c158be67d68533670'
step_id: 'S88'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh resolve the command-line lifecycle module that asserts custody verbs are mounted

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`

## Description

- Establish per test which verbs are actually absent and why each test fails,
  rather than assuming a shared cause.
- Repoint the assertions whose retirements are settled.
- Keep the one gap that has no ruling behind it visible.

## Outcome

Three of the five asserted verbs are absent, not one -- the extent had been
hidden by iteration order. Measured by direct invocation with the exit captured
unpiped, and the module's failures split three ways rather than sharing a cause.

The retired verbs are now checked in the RETIRED direction: an assertion that
they remain unmounted, so a silent reinstatement fails. Each retirement is named
individually in the commit message with its own reason -- one spelling deleted
rather than renamed under the single-verb rule, and two retired with the
shared-master recovery lifecycle -- so a future reader finding them absent learns
they went by decision rather than by loss, and does not restore the assertion and
repeat the investigation.

Four further failures in the same module belong elsewhere entirely: they never
reach a custody verb, failing at profile creation on a deliberate permanent
refusal. They are more instances of an open product ruling rather than defects
here, and were deliberately not fixed, because fixing them would encode an answer
nobody has given.

**One assertion is left deliberately RED, and that is the point of the step.** An
operator cannot rotate their profile passphrase by any surface: no command, no
application-layer rotation function, only unorchestrated primitives in the
custody package. In an application whose load-bearing guarantee is that financial
data lives solely under that credential, the absence of credential rotation is a
product question rather than test staleness. The assertion fails naming the gap,
with both a docstring and an inline comment stating the test is not broken, so
the next reader meeting a red test in a green module does not delete it.

## Notes

The author initially removed that assertion entirely and documented the reasoning
in prose, which made the module green and the missing capability invisible -- the
exact outcome both dispatcher and author had argued against, contradicting the
author's own stated principle. They caught it, restored the assertion as a
deliberate failure, and landed the correction as its own commit rather than
amending, so the history records why the first shape was wrong.

The bite proof had to cross a process boundary: this module shells out, so an
in-process patch cannot reach the spawned interpreter. The injection rides an
automatically-imported module on the interpreter path, and the reinstated verb
printing its own help is precisely the silent reinstatement the retired-direction
assertion exists to catch. Most attempts at that proof would have failed to
inject and reported the resulting green as evidence.

A fifth instance of the campaign's recurring prose defect was fixed alongside:
a docstring describing the retired creation mode as one that always registers the
full set of facts, present tense, directly above the permanent refusal. Every one
of the five has been documentation asserting a live behaviour the tree had
already retired, and every one was found while investigating something else.
