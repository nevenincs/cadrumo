---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:9e801f4db5b2a5dd0a3f04a012321e7e829335c822842a78400cac9831f1528f'
step_id: 'S78'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Replace previous-filing revision-selector mutation with real registry input

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_validate_previous_filing_year_coverage.py`

## Description

- Build immutable Modelo 100 definitions from real loaded revision objects with one target revision omitted.
- Replace revision-selector monkeypatches with those typed registry inputs.
- Preserve widened-gap, stale-allowance, and mid-range-gap discrimination through the production validator.

## Outcome

Previous-filing source-year coverage is now tested without mutating the revision selector or registry authority. The 2020 omission produces the widened gap and stale allowance, while the 2022 omission produces the distinct mid-range gap against real revision data.

## Notes

All eight focused tests passed in 29.14 seconds. The focused repository no-monkeypatch gate passed after this change, and Ruff, format checking, diff integrity, prohibited-control inventory, and independent review were clean. No production API change was necessary; the semantic discovery service was degraded, so exact source and governing-document fallback was used.
