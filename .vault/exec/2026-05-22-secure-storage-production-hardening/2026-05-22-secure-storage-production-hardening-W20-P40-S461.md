---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S461'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Record the D1 hard replacement of config unlock with config switch and enforce the no-alias compatibility contract

## Scope

- `src/aeat/entrypoints/cli/_config`
- `src/aeat/entrypoints/cli/tests`
- `src/aeat/locales`
- `.vault/adr`

## Description

- Reconstructed the custody-command contract from the accepted D1 decision and commit `f2e1b0c5ef`.
- Confirmed `config unlock` has no alias or compatibility shadow and resolves to Click's no-command result.
- Confirmed `config switch` resolves and the real profile-lifecycle integration suite passes.

## Outcome

The D1 hard replacement is implemented across command registration, contract tests, localized guidance, and operator documentation. This exact historic execution record closes the traceability gap without reintroducing a retired command.

## Notes

The current CLI returns exit code 2 for the deliberate no-command result; W22 P44 reconciles stale older `unlock` wording.
