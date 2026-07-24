---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S25'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Migrate the modelo work wizard consumer onto the engine frontends

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_work_wizard_cli.py`

## Description

- Project the discovered registry steps (manual casillas, promptable bindings, relation follow-ups) into a runtime FlowDefinition whose copy slots are schema-field references served by a per-run registry-derived table.
- Walk the steps through the line-mode flow frontend, preserving the empty-step scripted-caller short-circuit and the follow-up discovery loop.
- Extend the substrate copy registry to multiple resolvers per kind (first non-None wins) so modelo and profile schema-field namespaces coexist.

## Outcome

The modelo work wizard no longer imports the one-shot prompter surface; prompts, help, review, and the console refusal all ride the substrate. Verified headlessly (definition projection, copy resolution, scripted walk, follow-up append) with the flows suite green.

## Notes

The review surface changes the interaction (re-edit by number and an explicit submit step replace straight-through prompting); the emitted envelope and payloads are unchanged.
