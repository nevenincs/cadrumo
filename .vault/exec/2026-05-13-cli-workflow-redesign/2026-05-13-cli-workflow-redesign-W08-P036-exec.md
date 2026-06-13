---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W08.P036'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr]]'
---

# `cli-workflow-redesign` `W08.P036`

Completed the backend implementation phase for profile-associated secure buckets.

- Created: `src/aeat/application/profile/_repository.py`
- Modified: `src/aeat/application/profile/_actions.py`
- Modified: `src/aeat/application/workflow/_models.py`
- Modified: `src/aeat/application/wizard/_persistence.py`
- Modified: `src/aeat/application/filing/runtime.py`
- Modified: `src/aeat/core/errors/registry/_domain.py`

## Description

Profile-bound values now persist only through `PROFILE_BUCKET_NAMESPACE` as
`Envelope[ProfileBucket]` with `SensitivityClass.IDENTITY`. Workflow state stores
active profile pointers, and active profile reads dereference those pointers
through `profile_bucket_repository().load(...)`.

The wizard persistence path writes profile-bound answers through
`set_profile_values`. Filing runtime projection resolves the active profile
bucket before constructing `FilingOperatorProfile`. Profile bucket persistence
errors are registered under the central `AeatError` registry, and the modelo
calculation registry error discovered by the end-to-end import gate is also
registered centrally.

Closed plan rows: `W08.P036.S0211`, `W08.P036.S0212`,
`W08.P036.S0213`, `W08.P036.S0214`, `W08.P036.S0215`,
`W08.P036.S0216`.

## Tests

`uv run --no-sync pytest src/aeat/application/profile/test_actions.py src/aeat/application/workflow/test_adapters.py src/aeat/application/wizard/test_status.py src/aeat/application/wizard/test_status_next_action.py -q`
