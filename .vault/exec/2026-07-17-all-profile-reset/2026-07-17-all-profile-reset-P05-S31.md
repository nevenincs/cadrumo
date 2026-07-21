---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S31'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Sweep the MCP identity gate off the sandbox-use grammar onto switch-based sandbox addressing, updating its identity-changing command set and docstring

## Scope

- `src/cadrumo/entrypoints/mcp/_identity_gate.py`

## Description

- Remove `config.profile.sandbox.use` from the MCP identity gate's `ACTIVE_IDENTITY_CHANGING_COMMANDS` set (`_identity_gate.py`), so identity re-arming keys on the switch-based grammar (`config.switch` already covers sandbox entry by canonical label).
- Retarget the gate docstring off the removed `sandbox use` door onto switch-based sandbox addressing.

## Outcome

The MCP identity gate carries no sandbox-use grammar: `rg "sandbox.use|sandbox_use" src/cadrumo/entrypoints/mcp/` returns nothing, and `ACTIVE_IDENTITY_CHANGING_COMMANDS` is exactly `{config.switch, config.profile.create, config.profile.logout}`. MCP schema/parity/identity suite green (263 passed).

## Notes

This sweep was landed atomically WITH the sandbox `use` verb removal in commit `00c3ab005d` (P04.S19), per the relocation-atomicity rule (the consumer sweep rides the canonical change in one commit). This step is the bookkeeping enrolment the rescope reconciliation requested — the code change is not re-committed; only this exec record and the plan enrolment are added.
