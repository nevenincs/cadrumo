---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:fe5ff55ddb7798f7d44491f7a515cf98f740d84c208b12aca94c65686a6f32e3'
step_id: 'S58'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Canonicalize the overview CLI backend fixture shape at its narrowest owner

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_overview_verbs.py`
- `src/cadrumo/entrypoints/cli/conftest.py`

## Description

- Move the overview backend lifecycle to the CLI package conftest.
- Preserve function scope while replacing module-local autouse with explicit
  module-wide `usefixtures` activation.
- Prove that unrelated CLI tests do not activate the fixture.

## Outcome

The overview backend fixture has one canonical owner. All seven overview tests collect,
and an unrelated CLI setup trace passed without activating `_isolated_backend`. The
profile ID, nested storage/profile contexts, workflow update, minimal-profile
registration, yield, and teardown remain unchanged. An independent review found no
S58-owned issue.

## Notes

Semantic RAG discovery was unavailable, so exact source and census discovery supplied
the fallback evidence. Focused overview execution reaches the unchanged setup route but
is blocked because the current production facade no longer exports
`profile_create_storage_span`. The same missing symbol blocked the pre-change module;
no compatibility bridge or out-of-scope facade change was introduced.
