---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:0cf731a3012292a7b1e87265753160a15d5f66aed810334f9ab793cc3b5e7e68'
step_id: 'S28'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Run the suite under the newer interpreter and raise the declared floor to the account range

## Scope

- `pyproject.toml`

## Changes

M pyproject.toml
M uv.lock

## Notes

Verified by building the wheel, installing it into a 3.14 environment, and running
both console scripts there: the command reports its version and renders its full
command tree, and the agent server responds. That is the artifact a user receives.

The development test suite was not executed on 3.14: doing so needs the whole developer
toolchain resolved for that interpreter, which the frozen environment does not carry.
The closure resolves and every compiled dependency publishes 3.14 wheels for all three
shipped platforms, so nothing is known to block it.
