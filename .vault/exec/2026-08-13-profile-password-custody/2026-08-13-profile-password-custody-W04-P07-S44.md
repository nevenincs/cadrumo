---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:23d51d26ad2b4c52b9df61c58a8fbde6ecf72ecd3c02890bcb62cfa57b7f02bc'
step_id: 'S44'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule whether the operator-scope refusal introduced alongside the capsule cutover is intended, since it replaced a session fallback with a raise that two unguarded callers now hit where they previously succeeded, then pin that refusal with coverage, which it has never had on any of its twenty references

## Scope

- `src/cadrumo/application/auth/_operator_scope.py`

## Description

- Establish by reading the live callers, rather than by reading the refusal's
  name, which of them reach the raise and what each did before it.
- Rule the refusal intended, and separate it from the unrelated conflict
  refusal whose message it had been borrowing.
- Give the custody-session requirement its own error with an actionable
  message, so the operator is told what is missing rather than told to choose
  between two flags they did not pass.
- Pin the refusal with real coverage across the surfaces that reach it.

## Outcome

The refusal is intended and now says so in its own voice. It previously raised
the scope-conflict error, whose operator-facing text instructs the reader to
pass only one of two flags; that instruction is unrelated to the actual
condition, so every operator meeting this refusal was sent somewhere useless.
That is the campaign's recurring shape once more, a surface that is WRONG about
the system rather than merely silent, and it is the reason the fix was an error
of its own rather than a reworded message.

The caller ruling divides on whether the caller can answer honestly without a
session. The credential resolver correctly returns empty, because "no
credentials are available" is true whether or not custody is open. The three
verdict-rendering surfaces correctly raise, because a silent "not available"
there would be indistinguishable from "inspected and found nothing" when in
fact nothing was inspected. That distinction, not caller convenience, is what
decided each site.

Coverage is real and was verified independently of the authoring agent's
report: the full auth suite runs 227 passed, 0 failed, in 63 seconds. The pin
bites -- patching the session-reuse predicate to always agree reds seven of the
ten tests that observe it.

## Notes

The refusal had twenty references and no coverage at all before this step, which
is how a raise could be substituted for a fallback without anything noticing.
The count of references is not itself the defect; the absence of a single test
asserting which condition produces which error is.
