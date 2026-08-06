---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:996ec0948413d69546c67b2bdbb3512f0122a35cc9a8ef6f96e788801dd9d9c1'
step_id: 'S13'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W02.P04.S13`

Scope: `src/aeat/core/aggregation.py`.

## Description

- Added the `CounterpartSourceKind` type alias for the canonical counterpart
  source-kind subset.
- Added `COUNTERPART_SOURCE_KINDS` and `counterpart_source_kind()` as the shared
  narrowing surface.

## Outcome

The counterpart source-kind subset is now owned by `aeat.core.aggregation`
instead of duplicated between application and registry modules.

## Notes

The retired bare `invoice` enum member remains available for persisted-registry
rejection paths, but is not part of the counterpart subset.
