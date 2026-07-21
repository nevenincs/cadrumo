---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S32'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Require a complete same-cohort evidence set in release readiness

## Scope

- `dev/release/readiness.py`

## Description

- Replace the newest-legacy-smoke advisory in the aggregate release report with a
  blocking exact-cohort evidence gate.
- Declare the twelve pre-publication Python, Scoop, Homebrew, Claude plugin, and MCPB
  rows that collectively support the advertised platform and client surface.
- Require the cohort source commit to equal the checked-out Git commit and its tag to
  equal the cohort version tag.
- Load every retained result against the same validated cohort bytes and require at
  least one passing record for every declared row.
- Invalidate the cohort on any failed row and require real client identity for every
  Claude-dependent row.
- Reconcile release version readiness with the cohort-embedded MCPB bootstrap, whose
  exact wheels are injected during bundle assembly instead of named by a template
  `uvx` pin.

## Outcome

- Release readiness now fails closed when the release cohort, evidence directory, a
  required row, exact source revision, exact version tag, or client identity is absent.
- Unrelated prior manifests and advisory smoke success cannot authorize publication.
- The release report and JSON CLI return a blocking verdict until installed evidence
  for the complete required set exists.
- Focused formatting, Ruff, and type checks passed. The combined readiness suite passed
  all 33 direct tests.

## Notes

- The current working release is intentionally not ready: the required platform and
  real-client observations have not all executed and therefore no complete evidence
  directory exists.
