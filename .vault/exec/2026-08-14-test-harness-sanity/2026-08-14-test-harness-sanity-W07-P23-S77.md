---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:58e5386bc93c854c55f8e3d24c6b400e4045e678b05bfa23a21292b58e21c567'
step_id: 'S77'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Replace relation-allowance mutation with an explicit production input

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_relation_closure.py`

## Description

- Expose typed source-year coverage allowances as an explicit validation input with the production table as default.
- Replace relation-allowance monkeypatches with direct matching, stale, narrow, and widened allowance values.
- Keep allowance diagnostics accurate for both built-in and caller-supplied inputs.

## Outcome

Relation closure allowance behavior is now exercised through the production validator API without mutating its private allowance table. Default production callers remain unchanged, while tests supply real typed values that discriminate valid suppression from stale and over-wide coverage.

## Notes

The first implementation retained a diagnostic that always named the private `_ALLOWANCES` table; independent review required source-neutral wording. The corrected controls passed directly through production code, two focused allowance tests passed, adjacent default behavior passed, and Ruff, format checking, diff integrity, and target forbidden-control inventory were clean. Full module collection remains blocked by an unrelated missing profile-custody export.
