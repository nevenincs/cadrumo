---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:963eb6d03aae7dd9621a00c81c807c6c3fa41e52d7a8ed27af4705c1c202158f'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` audit: `S43 active-refusal disposition review`

## Scope

Independent review of commit `3baa9b9f01`, limited to the active-refusal
owner-disposition invariant in `src/cadrumo/application/registry/_closure.py`
and its contract tests.

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

Focused verification passed: Ruff for the changed module and contract test,
and `pytest -x src/cadrumo/application/registry/tests/test_closure_models.py`
with 7 passing tests. An external runtime mutation removed the model validator
only in the test subprocess; the resulting model admitted the forbidden
`refused` plus `resolved` disposition, proving the regression path would fail
without the validator. `git diff --check 3baa9b9f01^ 3baa9b9f01` also passed.

## Recommendations

No follow-up is required.
