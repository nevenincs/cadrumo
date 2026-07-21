---
tags:
  - '#exec'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-09'
step_id: 'S11'
related:
  - "[[2026-07-08-mcp-identity-linked-operation-plan]]"
---

# Author the Erik/Erika profile-switch golden scenario where a mutation under the wrong active profile must be blocked until identity is re-confirmed

## Scope

- `src/aeat/agent/eval/scenarios/identidad_perfil.toml`

## Description

## Outcome

Landed in commit d0b4dc7688 — Erik/Erika scored eval: score_identity_trajectory replays the real identity_gate_refusal (no re-implementation); the wrong-profile hazard fails the scenario; anti-tautology guard.

## Notes
