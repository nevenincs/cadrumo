---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W08.P038'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr]]'
---

# `cli-workflow-redesign` `W08.P038`

Completed cleanup of rejected profile storage compatibility surfaces.

- Modified: `src/aeat/application/profile/test_actions.py`
- Modified: `src/aeat/application/config_reset.py`
- Modified: `src/aeat/application/setup_reset.py`
- Modified: `src/aeat/application/wizard/_status.py`
- Modified: `src/aeat/entrypoints/cli/deadlines/__init__.py`
- Modified: `src/aeat/adapters/persistence/storage/_rotation.py`
- Modified: `src/aeat/adapters/persistence/storage/_test_rotation.py`

## Description

Removed stale prose and test assumptions that described workflow state or
profile-path files as profile value storage. Rotation comments now refer only to
remaining single-file consumers. Reset documentation describes both workflow
pointer removal and profile bucket deletion.

Closed plan rows: `W08.P038.S0223`, `W08.P038.S0224`,
`W08.P038.S0225`, `W08.P038.S0226`, `W08.P038.S0227`,
`W08.P038.S0228`.

## Tests

`uv run --no-sync ruff check src/aeat/application/profile/test_actions.py src/aeat/application/config_reset.py src/aeat/application/setup_reset.py src/aeat/entrypoints/cli/deadlines/__init__.py src/aeat/adapters/persistence/storage/_rotation.py src/aeat/adapters/persistence/storage/_test_rotation.py`
