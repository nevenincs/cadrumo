---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:90543710092f12b6b676237c23293b43722c0c8bd4171428219fc56162ccee70'
step_id: 'S82'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Align worker tests with repository-owned six-worker authority and explicit overrides

## Scope

- `src/cadrumo/tests/_worker_count_hook.py`
- `src/cadrumo/tests/test_worker_count_hook.py`

## Description

- Align worker-policy terminology with the accepted repository-owned auto-width decision.
- Prove the project worker variable overrides xdist's native environment variable.
- Prove unset or invalid project configuration resolves to six and explicit `-n` bypasses auto resolution.
- Remove the misleading cap constant name without retaining a compatibility alias.

## Outcome

The installed root hook remains the sole repository resolver for `-n auto`: `CADRUMO_PYTEST_WORKERS` wins when valid, otherwise the repository selects six, while explicit process counts bypass the hook. The native xdist environment variable no longer has ambiguous authority in either implementation wording or real-process tests.

## Notes

The runtime behavior already matched the accepted successor decision; the change strengthens naming and discriminating evidence. Twelve pure unit cases, four installed-hook subprocess cases, three actual root-route probes, five CI width-policy cases, Ruff, formatting, type checks, diff integrity, and independent review passed. Semantic RAG was unavailable in the local service environment, so exact source and Vault fallback discovery was used.
