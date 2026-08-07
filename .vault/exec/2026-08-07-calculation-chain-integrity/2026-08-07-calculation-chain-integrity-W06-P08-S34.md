---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f80b336ff0dd6c4bad41d41cf1575056831c59202c98517732a08fb5f039f167'
step_id: 'S34'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S34

## Outcome

Checked before the addition, and the check is preserved as a test rather than as a note.

## The hazard

Adding `DOMESTIC_NOT_SUBJECT` to the cash-accounting exclusion set would newly refuse rows for a taxpayer who is BOTH not-subject and on the cash-accounting regime. The Step flags that this combination is live via the OSS declaration path, so the addition could have turned working rows into refusals.

## What the check established

The refusal is correctly scoped: it fires only when the row is actually under the cash-accounting regime, not merely because the category is not-subject. That scoping is pinned by `test_a_not_subject_row_outside_the_regime_is_not_refused_by_this_gate` (`application/aggregation/tests/test_iva_cash_accounting.py:313`), where a not-subject row outside the regime passes through untouched.

So an OSS row belonging to a taxpayer who also uses cash accounting is refused only on the rows genuinely inside the regime, which is the intended treatment rather than a regression.

## Why this is recorded separately from S43

The Step exists because the check had to happen BEFORE the set membership changed. Recording it separately keeps that ordering visible: the addition in `S43` is safe because of this finding, not independently of it. Collapsing the two would lose the reason the addition is not a regression.
