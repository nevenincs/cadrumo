---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W05.P022'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-root-help-shape-adr]]'
---



# `cli-workflow-redesign` `W05.P022`

Completed the shadow duplicate removal phase for root help and discovery
behavior.

- Modified: `src/aeat/application/operator_surface/_contract.py`
- Modified: `src/aeat/application/operator_surface/test_contract.py`
- Modified: `src/aeat/entrypoints/cli/test_root_help_shape.py`

## Description

Consolidated help discovery around the backend operator surface inventory.
The accepted root and mounted command family contract is the source of truth
for the root/config/app discovery pages. Tests assert that retired roots and
phantom command families are excluded from curated help, preventing stale
surface names from reappearing through presentation copy.

Closed plan rows: `W05.P022.S0127`, `W05.P022.S0128`,
`W05.P022.S0129`, `W05.P022.S0130`, `W05.P022.S0131`,
`W05.P022.S0132`.

## Tests

`uv run --no-sync pytest src/aeat/application/operator_surface/test_contract.py src/aeat/entrypoints/cli/test_root_help_shape.py -q`

`uv run --no-sync pytest src/aeat/application/operator_surface/test_contract.py src/aeat/application/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_root_help_shape.py src/aeat/entrypoints/cli/test_profile_output_language.py src/aeat/core/i18n/test_output_language.py -q`
