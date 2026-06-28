---
step_id: S03
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W01.P01.S03 — real-behavior BucketId unit tests

## Scope

Pin the BucketId alias boundary contract with real-behavior pytest cases
that build a populated pydantic `BaseModel` and assert
`pydantic.ValidationError` on the rejection paths.

## Outcome

`src/aeat/core/identity/test_bucket.py` exercises six properties:
valid construction, empty rejection, max-length rejection, max-length
acceptance (128 characters), surrounding-whitespace strip, and
whitespace-only rejection after strip.

## Verification

`uv run --no-sync pytest src/aeat/core/identity/test_bucket.py -x -q`
reports `6 passed`.

## Commit

`c0c8c28a2` — test(core/identity): real-behavior unit tests for BucketId constraint
