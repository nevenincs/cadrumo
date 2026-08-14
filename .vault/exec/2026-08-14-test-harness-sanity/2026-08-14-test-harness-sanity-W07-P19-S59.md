---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:afec9efaf3c129a9577fe9e5b0934efa64433adb0acda88058785b47ecad2347'
step_id: 'S59'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Canonicalize the open-bucket CLI backend shape without merging storage lifecycles

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_ledger_view_ux.py`
- `src/cadrumo/entrypoints/cli/conftest.py`

## Description

- Move the open-ledger bucket lifecycle to a public CLI conftest fixture.
- Preserve per-test activation through module-level `usefixtures` without broadening
  activation to unrelated CLI tests.
- Give the S58 overview lifecycle its own public, collision-free fixture name.

## Outcome

`open_bucket_cli_backend` is the single owner of the former ledger-view fixture body.
It retains function scope, the `tmp_path` dependency, and the complete
`_open_ledger_ux_session` context and teardown. `overview_cli_backend` remains a
separate lifecycle, and the S57 profile-root fixtures remain unchanged. An unrelated
CLI setup trace used neither canonical fixture. Ruff and diff checks passed, and an
independent review found no S59-owned issue.

## Notes

Semantic RAG discovery was unavailable, so exact source and census discovery supplied
the fallback evidence. The ledger-view module cannot currently collect because its
pre-existing support import requests the removed `profile_create_storage_span` facade.
That failure predates this relocation and prevents a green fixture lifecycle run; no
compatibility bridge or out-of-scope facade change was introduced.
