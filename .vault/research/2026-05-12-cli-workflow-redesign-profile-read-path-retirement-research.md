---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `profile-read-path-retirement`

## Findings

Production profile reads have moved to workflow state. The deadlines helper
already uses `workflow_state_repository().load()` and
`load_active_autonomo_profile`, and filing runtime reads active workflow state.
The legacy `load_profile_envelope` symbol is gone from production; only
envelope-era constants remain in setup environment writer code.

Drift remains in docs and tests that reference `--profile PATH` and
`AEAT_DEFAULT_PROFILE_PATH` for deadlines. The target decision is to keep
workflow-state reads as the only production path and retire all operator-facing
profile-file affordances.

Reject flat-file fallback reads, dual read paths, compatibility environment
variables, `--profile PATH`, and profile-envelope references in operator CLI,
tests, and docs.
