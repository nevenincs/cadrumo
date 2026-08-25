---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:3d91f8794fd1b1c5e01c276e3e79dd8f79fbaa61f9b2057d95a5b334fa984f0b'
step_id: 'S79'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate portal recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/application/portals`

## Description

Reconciled the portal application scope against the live action census and current refusal contract.

## Outcome

- The live action census reports zero candidates in the portal application scope.
- The sole portal refusal uses a registered message identity and machine fact without authored command or recovery prose.
- Co-located structural tests prohibit authored messages, producer-side locale resolution, and runtime CLI-command strings.
- Verification: portal suite — 32 passed; focused ruff — clean.
- Independent review: PASS.

## Notes

No production change was required; the implementation had landed while the plan checkbox drifted.
