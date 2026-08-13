---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:dbcd7cafb9e710f33617359b8dd4fdb2c52dd3fdf89769689cc20e75a7361537'
step_id: 'S12'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---
# add a golden-schema pinning test capturing `ExpedienteDeclarationPayload`'s advertised `model_json_schema()` before and after `W02.P02.S11`, so the CLI/MCP contract change is a visible reviewed diff rather than a silent constraint shift

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_expediente_declaration_payload_schema_pin.py`

## Description

- Read `ExpedienteDeclarationPayload.model_json_schema()` from the production output model as the sole schema authority.
- Pin the complete advertised `expediente_id` property fragment as one reviewed literal: string type, title, 12-character minimum, 32-character maximum, and the canonical uppercase-alphanumeric pattern.
- Assert that `expediente_id` is a required property before comparing its fragment, so a missing or non-required field cannot satisfy the pin.
- Import the production output model directly from its owning CLI payload module; do not duplicate its alias, validator, or schema construction.

## Outcome

The declaration-row schema advertises the same constrained AEAT expediente identifier to CLI and MCP consumers because both surfaces derive their schema from the registered output model. A future missing field, removal from the required set, reversion to a bare string, or any fragment drift fails the focused contract test.

## Notes

Focused pytest, Ruff lint and format checks, Ty, and whitespace validation pass for the test. The wider repository has concurrent unrelated work; this Step changes no production schema or unrelated identifier surface.
