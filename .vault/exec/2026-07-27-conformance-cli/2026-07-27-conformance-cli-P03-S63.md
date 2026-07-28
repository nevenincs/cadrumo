---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S63'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# default the review date on a reviewer-only restatement so a re-attributed review cannot inherit the previous reviewer date and record a person as having reviewed on a day they did not

## Scope

- `dev/registry/conformance/_stamp.py`
- `dev/registry/conformance/cli.py`
- `dev/tests/test_registry_conformance_cli.py`

## Description

- Add the refusal that fires when a DIFFERENT reviewer is supplied with no date
  while the manifest declares one.
- Record the ruling in the module docstring and at the guard, naming the act each
  alternative would silently rewrite.
- Record at the CLI's today-defaulting why it is not widened to cover this path,
  so the next reader does not close the hole by re-opening the trade.
- Restate the date in the existing vocabulary-guard test, which performed the
  now-refused act, and assert the date moved with the reviewer.
- Add the refusal case proved on bytes, and two paired positives: a reviewer
  change stating its date, and the two acts that inherit a date honestly.

## Outcome

### Ruling: refuse, do not default the date to today

The sweep's measurement reproduced exactly against a byte copy of the shipped
Modelo 130 tree before anything was changed:

```
seeded : agent_reviewed | agent:first | 2026-01-15
stamp --reviewed-by agent:second
after  : agent_reviewed | agent:second | 2026-01-15
```

Both candidate behaviours close that smear, so the choice turns entirely on what
each does to the act it is NOT thinking about, and that act is the typo
correction.

Defaulting the date to today whenever the reviewer moves makes a name correction
rewrite the date of a real review. The review genuinely happened on 2026-01-15;
only the spelling was wrong. So defaulting trades one false date for another,
and the tool cannot tell the two cases apart, so it would always guess. The
current inherit-the-declared-date behaviour is the same failure mirrored: correct
for a typo correction, false for a genuine re-review. Both silently pick an
interpretation of an ambiguous request.

Refusing is the only option that makes the caller state which act they are
performing. It costs one argument and it makes the record say something the
caller actually asserted. It is also the shape this writer already applies one
function away: a reviewer supplied against `pending_review` is REFUSED rather
than quietly dropped, on the stated ground that a caller must never be told the
write succeeded while their claim was altered. Widening the CLI's today-default
would have contradicted its own justification, which is that the review is
happening NOW — true when a status is being advanced, and asserting nothing at
all when only a name moves. That reasoning is now recorded at the defaulting
condition itself, because that condition is where a future reader would make the
change.

### The refusal is narrow by construction

It fires only on a CHANGE of reviewer against a declared date. Restating the same
reviewer inherits a date that is still that reviewer's own, so there is nothing
to smear; moving only the date is an explicit statement about the date, which is
the opposite of inheriting one; and a first review has no declared date to
inherit, so the advance path and the CLI's defaulting are untouched.

The existing vocabulary-guard test performed exactly the refused act — it stamped
`agent:first` on 2026-07-27 and then re-attributed to `agent:second` with no date
— and asserted only the reviewer. It now restates the date and asserts it moved,
so the test that used to demonstrate the defect demonstrates its absence.

### Verification

Two mutations, in opposite directions, each flipping its own assertion and
leaving the other side alone.

Neutering the guard:

```
E   Failed: DID NOT RAISE StampError
FAILED ...::test_stamp_refuses_a_new_reviewer_that_does_not_restate_the_date
1 failed, 3 passed in 34.45s
```

Widening it by dropping the same-reviewer early return:

```
E   StampError: refusing to record reviewed_by 'agent:first' without a date: the
    manifest declares the review as 'agent:first' on 2026-01-15 ...
FAILED ...::test_restating_the_same_reviewer_or_only_the_date_stays_legal
1 failed, 3 passed in 9.96s
```

The second is the one that proves the paired positives are load-bearing: a guard
refusing every reviewer argument would satisfy the refusal case while making the
tool unable to correct its own record, and without that case no assertion in the
file would notice. Both mutations were reverted and the module re-verified.

Full dev CLI module under the DEFAULT selector:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
67 passed in 76.82s
```

Style and lint:

```
uv run --no-sync ruff format --check ...  -> 3 files already formatted
uv run --no-sync ruff check ...           -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator
direction; the service is stopped and its index is broken. Grounding was by
whole-file reads and `rg`.

The verb was NOT run against the shipped registry. Every write was against a byte
copy of the real Modelo 130 tree.

The Step row's own wording asks for the date to be DEFAULTED. The row was
executed as a refusal instead, for the reason recorded above, and the row's
intent — that a re-attributed review cannot inherit the previous reviewer's date
— is met either way. The divergence is deliberate and is named here rather than
left for a reader to infer from the diff.
