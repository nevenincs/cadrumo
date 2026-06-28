---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W08.P039'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr]]'
---

# `cli-workflow-redesign` `W08.P039`

Completed real behavior verification for bucket-backed profile values.

- Modified: `src/aeat/application/profile/test_actions.py`
- Modified: `src/aeat/application/archive/test_archive.py`
- Modified: `src/aeat/application/test_config_parity.py`
- Modified: `src/aeat/entrypoints/cli/filing/test_filing_cli.py`
- Modified: `src/aeat/entrypoints/cli/test_workflow_surface.py`

## Description

Added and updated tests so profile bucket behavior is exercised through real
repositories and real CLI command paths. The archive test now round-trips a
profile bucket through the secure-object archive adapter. Filing tests seed
drafts through the secure repository rather than through removed JSON-input CLI
surface. The end-to-end test covers config init, config profile set/get/status,
overview calendar readiness, and filing runtime projection through the same
profile bucket.

Closed plan rows: `W08.P039.S0229`, `W08.P039.S0230`,
`W08.P039.S0231`, `W08.P039.S0232`, `W08.P039.S0233`,
`W08.P039.S0234`.

## Tests

`uv run --no-sync pytest src/aeat/application/profile/test_actions.py src/aeat/application/archive/test_archive.py src/aeat/application/test_config_parity.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/entrypoints/cli/test_workflow_surface.py::test_config_init_profile_set_deadlines_and_filing_runtime_share_profile_bucket -q`
