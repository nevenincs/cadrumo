---
tags:
  - '#exec'
  - '#homebrew-arm64-pac-ret'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:92e800fdf89cde1c6c74f151a366c2466570864d05dc4eee0f05ff1170f21276'
step_id: 'S01'
related:
  - "[[2026-07-25-homebrew-arm64-pac-ret-plan]]"
---

# Bring the self-hosted Linux ARM64 runner back online, since it was offline at record time and no diagnosis can proceed without it, OPERATOR-GATED as a host action

## Scope

- `operator action`
- `self-hosted Linux ARM64 host`

## Description

- Enumerate the self-hosted runner fleet through the forge Actions API and read each runner's status and busy state.
- Confirm the Linux ARM64 runner is registered with the labels the Homebrew acquisition matrix selects on.

## Outcome

The Linux ARM64 runner is online and idle, verified 2026-07-28: status `online`, `busy=false`, labels `self-hosted, Linux, ARM64`. The step's premise no longer holds -- the host was offline when the plan was recorded and has since returned -- so no operator host action was required to satisfy it.

The acquisition matrix's Linux arm64 leg therefore has a runner to land on.

## Notes

Verification is a live fleet read, not a recorded claim: the runner's own registration was queried at close time rather than inferred from the absence of a failure.

A separate fleet fault surfaced during the same read and is recorded under `S04`: the Linux X64 runner, which the acquisition workflow needs for its evidence-draft, x86-64, and seal jobs, was dead. That is a different runner from this step's subject and did not affect this outcome.
