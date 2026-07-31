---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:6fd8068dd9efedb8a5ffefef08faca56c8204c142b0c33af46e98fc0c6a89fe3'
step_id: 'S31'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Migrate the amend wizard consumer onto the engine frontends, removing its local one-shot prompt helper

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_amend_wizard_cli.py`

## Description

- Rebuild the amend wizard as a flow definition on the shared substrate (per-run copy table under the `modelo-amend` namespace, two-round flow) and drive it through the capability-selected frontends.
- Remove the module-local one-shot prompt helper the amend path had re-homed during the earlier consumer break-fix.
- Keep the non-interactive branch on the scripted intent driver so both transports share one flow authority.

## Outcome

Landed at commit `ab1d352f61`. The amend wizard walks the same engine, frontends, and validation as the setup flow; no local prompt implementation remains in the module. Its conformance and CLI tests are green.

## Notes

- This step completed the consumer sweep that unblocked the atomic retirement in `S26`.
