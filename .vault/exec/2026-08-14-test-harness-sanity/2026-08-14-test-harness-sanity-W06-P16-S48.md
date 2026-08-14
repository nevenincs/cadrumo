---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:c456a0cc7a6335d283f796a010de79a16f7ef25e54b6f2c79b1545f3a1e888eb'
step_id: 'S48'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Add real-tree census tests that prove root source development and packaging coverage and reject collapse

## Scope

- `dev/quality/tests/test_fixture_census.py`

## Description

- Exercise the census against a real temporary repository containing root, source, development, and packaging fixtures.
- Prove decorator, lifecycle, body, import, explicit-consumer, dynamic-request, and autouse-reach fields.
- Add discriminating nested-conftest import controls and fail-closed source-universe cases.

## Outcome

The fixture census now has bounded real-filesystem regression coverage for its complete public evidence model. The tests fail if imported fixtures or autouse fixtures stop reaching conftest descendants, if static or dynamic request routes disappear, or if required roots and readable parseable inputs collapse.

## Notes

The first test shape did not discriminate the earlier imported-through-conftest defect and was rejected during independent review. The corrected eight-test suite covers descendant parameter, `usefixtures`, static `getfixturevalue`, dynamic-request, and autouse routes without mocks, patches, skips, or fakes. Focused unit tests, Ruff, format checking, diff integrity, and final independent review passed.
