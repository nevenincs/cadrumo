---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:7a9d9cd28abb18ced4c7370ed43a6a82de0dbf895854748caba9ac347666c7d2'
step_id: 'S05'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Bridge the existing wizard catalogue vocabulary into FlowDefinition while keeping the compile_profile_keys projection and the register_wizard_catalogue and register_project_answers core slots fed unchanged

## Scope

- `src/cadrumo/application/flows/_bridge.py`

## Description

- Project the existing wizard catalogue descriptors into runtime FlowDefinition sections, pages, and choices without altering the descriptor vocabulary.
- Keep the compile_profile_keys projection and the register_wizard_catalogue and register_project_answers core slots fed from the same source, unchanged.
- Landed in `11cd31ddc8`; the module was later renamed from `_bridge` to `_wizard_projection` in `6b1949f5eb` to clear the shim-name gate.

## Outcome

The wizard catalogue now materialises a FlowDefinition the engine consumes, while the three registration projections keep receiving their original input. Pinned by the bridge tests in `10506c8833` (test_bridge.py, now test_wizard_projection.py after the rename). Reviewer finding M2 cleared.

## Notes

The relocation `_bridge` to `_wizard_projection` (`6b1949f5eb`) also moved the test file to test_wizard_projection.py; the shim name was refused by the naming gate.
