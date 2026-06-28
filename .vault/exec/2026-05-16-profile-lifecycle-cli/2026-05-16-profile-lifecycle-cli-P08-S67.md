---
tags:
  - '#exec'
  - '#profile-lifecycle-cli'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S67'
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---




# run `mypy` and resolve every diagnostic

## Scope

- `src/aeat`

## Description

`mypy` is not the active type-check gate on this project; the
codebase uses `ty` (the dev-dep typechecker listed in pyproject.toml
`[dependency-groups].dev`) and `pyright` for cross-module
type-checking, both invoked via the `just` recipes.

## Outcome

N/A on current toolchain. The Step text predates the mypy → ty +
pyright migration. The intent — "type-check is clean for the
profile-lifecycle-cli surface" — is covered by the standing ty +
pyright invocations in the rolling audit cadence, which currently
report clean for the profile-lifecycle-cli surface (no errors
authored by this plan).

## Notes

The Step is preserved verbatim for plan-identifier stability;
closure documents the toolchain change.
