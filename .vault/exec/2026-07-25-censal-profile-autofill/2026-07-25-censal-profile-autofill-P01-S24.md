---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S24'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Pin the session-identity comparison the certificate provider's only fail-closed check rests on, asserting the refusal and the per-return wiring rather than the expectation alone

## Scope

- `src/cadrumo/application/auth/tests/test_session_identity_comparison.py`

## Description

- Confirm at HEAD that the comparison carries four production call sites and zero
  test references, so the reported gap is current rather than already closed.
- Sweep the session module by syntax tree to establish that both live-session
  writers do call the comparison, ruling out a second, wider defect before
  writing cover for the reported one.
- Add refusal cases for a Cl@ve session and a certificate session bound to
  another taxpayer, deriving the expectation from the real resolver rather than
  a literal so each case exercises both halves of the guard joined.
- Add the matching-session control, without which a comparison that refused
  every session would satisfy both refusal cases.
- Pin normalisation, so a lower-case or padded NIF echoed back by an AEAT
  surface is not read as another taxpayer.
- Record that a bound session cannot carry a blank identity, which makes the
  comparison's skip-on-blank branch defence rather than exposure, and pin the
  one real fail-open: a profile with no fiscal ID has nothing to compare.
- Assert the wiring per return statement rather than per function, since a
  writer whose existing returns are guarded and whose new return is not is the
  precise shape being defended against.

## Outcome

The far half of the identity guard is covered. Refusal, acceptance and
normalisation are driven with real session records and a resolver-derived
expectation; no test doubles are involved, because the comparison reads an
identity off a bound session and nothing else.

Both teeth checks were run against a temporary local mutation, and the
production module was confirmed byte-identical to its committed state
afterwards in each case. Neutering the refusal reddens exactly the two
mismatch cases while the twelve existing expectation tests stay green, which
is the asymmetry that made the gap invisible. Deleting one of the four call
sites reddens the wiring assertion at the exact line, and propagates to the
delegating public entry point.

Verification: the seven new cases pass, and the surrounding auth application
suite passes at 216. Lint, format and type check are clean on the new file.

## Notes

The wiring assertion was wrong on its first two attempts, and only the teeth
check found either. It first swept the whole syntax tree and so flagged two
methods of the provider Protocols, which declare session-returning signatures
but describe what an outbound provider offers rather than what an application
writer must check; the sweep was narrowed to module level rather than the two
names being excused. It then passed with a call site deleted, because it
accepted the comparison appearing anywhere in a preceding sibling statement,
and a preceding branch guards its own return rather than the one under
examination. Requiring an unconditional call in the prefix of a block on the
route closed that.

The second failure is the substantive one: a wiring check that passes with the
wiring removed is worth nothing, and it looked correct until it was mutated. The
first attempt would have been caught by reading; the second would not.

The dominance rule is deliberately conservative. A refactor that moved the
comparison into a helper called unconditionally before a return would fail this
assertion despite being sound. That is the intended direction of error for a
check standing in for the certificate provider's only identity comparison, and
the failure message names the offending line so the reader can adjudicate.

The tree-wide marker gate is red at HEAD, in five files owned by other
campaigns and none of them touched here. It was left alone and reported.
