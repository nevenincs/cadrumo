---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:953375e20ad87c854cb9600ad270acfe9b3cd0c7f75cd3fea04105e7a19aa954'
step_id: 'S08'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Compose the source-connectivity limb from the canonical evidence-backed census authority

## Scope

- `src/cadrumo/application/registry/`

## Description

- Project the strict source-connectivity census onto every validated registry revision.
- Preserve only revision-resolvable destination candidates and carry their grounding into closure evidence.
- Refuse current candidate and blocked dispositions, mark expired evidence stale, and fail closed when census scope is absent.
- Export the report composer through the application-registry facade and generate its API-reference stub.

## Outcome

- Added `SourceConnectivityCoverageReport` and `compose_source_connectivity_coverage`.
- Added focused coverage for the complete revision denominator, current candidate refusal, missing scope, expired evidence, and terminal evidence.
- Passed `ruff check` for the touched Python files.
- Passed 12 focused registry tests in 30.25 seconds.

## Notes

- The package API toctree contains concurrent S06/S07 documentation work; this Step stages only the S08 generated entry through an isolated index.
