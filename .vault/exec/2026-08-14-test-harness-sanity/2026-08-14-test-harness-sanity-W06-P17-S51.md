---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:4e1b67cbf085ad49dccad0d02c267e84178ce248074e04865d33e3ec27e1659f'
step_id: 'S51'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Enroll the harness verdict in CI independently from unit and integration verdicts

## Scope

- `.github/workflows/ci.yml`

## Description

- Add a standalone per-push CI job for the deterministic harness verdict.
- Reuse the frozen bootstrap and canonical repository recipe.
- Keep the harness job blocking, independently timed, and free of unit-job dependencies.

## Outcome

Per-push CI now reports test-harness failures independently from static and unit verdicts. The job invokes only the canonical outer-serial recipe and has its own 25-minute failure boundary.

## Notes

Semantic discovery was attempted first, but the local RAG service was degraded. YAML parsing, diff integrity, the workflow structure checks, and independent review passed. A local full harness attempt surfaced unrelated broad shared-tree collection failures under temporary paths; it was not claimed as a green CI verdict.
