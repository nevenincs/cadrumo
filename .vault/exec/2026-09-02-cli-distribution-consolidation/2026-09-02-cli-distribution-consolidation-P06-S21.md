---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:6458d62df950d65e0fa1a9e32a510493db6b0de5f04d280ad1fa4d25c747426f'
step_id: 'S21'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Replace nested-container install proof with an isolated environment probe

## Scope

- `dev/packaging/smoke_core.py`

## Changes

D dev/packaging/smoke_docker.py
D dev/packaging/tests/test_smoke_docker_selection.py
M dev/packaging/campaign.py
M dev/packaging/tests/test_campaign.py

## Notes

No new probe was written. Five forms already prove the cohort installs and runs without
a container - a uv virtual environment, plain pip, an sdist build, the optional extras,
and the joined three-wheel cohort - and each holds the artifact under test and nothing
else. The container form's only additional claim was a clean operating system, bought
with a daemon the fleet cannot supply on every target, and it is the reason one declared
platform has never produced a passing row.
