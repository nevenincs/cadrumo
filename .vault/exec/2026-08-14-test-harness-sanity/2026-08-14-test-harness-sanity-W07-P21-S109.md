---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:7f99e96680b61593682de54d01fd5b3ee32e48be9e7ab1922dc19dca7e730e36'
step_id: 'S109'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---
# Classify factory-bound fixtures as manifest rows with per-binding identity and argument evidence

## Scope

- `dev/quality/fixture_ownership.py`
- `dev/quality/tests/test_fixture_census.py`

## Description

- Add a `FactoryFixtureCandidate` carrying a non-optional `resolved_factory`, so an unresolved binding cannot enter the manifest wearing the same shape as a resolved one.
- Scope the imported-binding walk to the fixture's own qualname, skipping nested definitions that are not the fixture itself.
- Count and surface `unresolved_call_assignment_count` as a stated limitation rather than absorbing it into the resolved population.

## Outcome

Factory-bound fixtures are now manifest rows with per-binding identity and the argument evidence that produced them, instead of being invisible to the census or silently merged with directly-defined fixtures.

The honest number matters more than the classification: 3404 call assignments remain unresolved, and the census prints that as an explicit limitation line rather than reporting only what it managed to resolve. A census that reports its successes and omits its blind spot reads as complete coverage; the limitation line is what stops the resolved count being mistaken for the whole population.

## Notes

The scope fix was found by reading the walk rather than by a failing test, and it is the kind of defect a passing suite hides: a nested helper inside a fixture body could contribute bindings attributed to the fixture, inflating apparent identity with values the fixture never closes over. Since the wrong attribution still produces a plausible row, nothing downstream would have objected.

This record was authored after the row was already checked, closing an execution-record gap rather than carrying it forward.
