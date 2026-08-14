---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:8f24f7a470e50266c8d77fd934a8b2fe7ef79f9db88ce363394ae041727f9881'
step_id: 'S70'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium triage the rehoming-ledger findings the repaired gate can now report

## Scope

- `dev/tests/test_error_code_default_recovery_rehoming.py and dev/quality/error_code_default_recovery_rehoming.py`

## Description

- Classify each of the three finding codes by cause rather than enumerating the
  findings.
- Test the obvious remedy for the largest code before recommending it.
- Distinguish a stale record from a true fact about source or about a plan.

## Outcome

The three codes have three DIFFERENT causes, and only one of them is a
regeneration. That split is the deliverable, and it is sharper than the
stale-versus-wrong framing the row was given.

**The largest code is genuine staleness whose obvious remedy does not work.** All
hundred and two divergences are real structural changes the record has not
absorbed, and none indicates a source defect -- the cleanest case being a raise
whose enclosing function was renamed while its normalised syntax hash stayed
byte-identical. But regenerating the record was tried in memory, writing nothing,
and it does NOT converge: it aborts on more than thirty entries, because the
generator will accept an owner only from an OPEN plan step whose declared scope
covers the path, and the code has moved into modules no open scope names. So the
remedy is to extend those scopes first and regenerate second. Testing the obvious
fix and reporting that it fails is worth more than recommending it untested.

**The second code is a correct gate reporting a WRONG PLAN, and it inverted on
reading.** The rule requires an open owner wherever a producer still authors a
raw sentence positionally -- which matters because the first positional argument
is what string conversion prefers, so such a site keeps a hardcoded English
sentence alive in tracebacks and logs in every locale while a key-and-context
assertion stays green. It is the machine evidence separating a migration awaiting
work from one that landed. So the finding means a step was marked complete while
producers inside its own declared scope were still unmigrated. Proven concretely:
one readiness-gate module carries migrated and unmigrated raise sites SIDE BY
SIDE under a single checked step accounting for twenty-four of the forty-two.
That is exactly the failure this project's orchestration rules name, where
delivered-as-specified and recorded-but-not-implemented wear the same checkbox.

**The third code splits.** Two entries are pure staleness, their classes deleted
by the capsule cutover. Four are source-wrong: classes still defined, still
exported, still registered, carrying documentation asserting behaviour, with zero
raise sites in production. One of those is a retention floor whose own
documentation calls it the refusal a destructive erase raises -- a guard the
codebase advertises and does not have, which in a filing-grade application is
worth more than dead-code hygiene.

Buckets: a hundred and four stale, forty-two plan-wrong, four source-wrong, and
**zero rule mis-specifications**.

## Notes

The count was reported as a hundred and fifty against the hundred and fifty-one
measured earlier, with the drift attributed to the tree moving between
measurements rather than chased or quietly reconciled.

The author recorded a GAP rather than implying coverage it did not have: the
analyser asymmetry it was warned about lives in export resolution, which now
passes, so no occasion arose to test it and no claim was made either way.

The most instructive part is the second code inverting on inspection. It looked
like a rule demanding an open owner for work that appeared done -- the very
shape that would justify amending the rule -- and reading what the rule actually
measures reversed it completely. That is the second time in this campaign an
agent has been one step from widening an analyser to accommodate a finding that
turned out to be correct.

The verified evidence for the plan-wrong code is one file holding both states,
with positional raises at two sites and keyed raises at three others.
