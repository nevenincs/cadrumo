---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:211a2bd7bcaababf5dda0b0248e29719b86b984a57fce6f3496f69173dfb1d53'
related: []
---

# `registry-completeness-closure` audit: `S43 active-refusal disposition review`

## Scope

The review checked Pydantic validation ordering, the refused and unmeasured
outcomes, preservation of satisfied behavior, and whether the regression test
detects removal of the guard.

## Findings

No findings. PASS.

The `mode="after"` validator receives typed nested refusal and disposition
models. Its new state check runs only after the satisfied early return and after
an unsatisfied limb has been required to carry a same-limb refusal, so it cannot
widen the satisfied contract or bypass the refused and unmeasured reason
invariants. The parameterized test covers both active outcomes with their
respective valid reasons.

An external runtime mutation removed the model validator only in the test subprocess; the resulting model admitted the forbidden `refused` plus `resolved` disposition, proving the regression path would fail without the validator. `git diff --check 3baa9b9f01^ 3baa9b9f01` also passed.

## Recommendations

No follow-up is required.
