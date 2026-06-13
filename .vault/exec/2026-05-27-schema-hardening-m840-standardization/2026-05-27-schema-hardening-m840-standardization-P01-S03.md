---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m840-standardization-plan]]'
---



# `schema-hardening-m840-standardization` `P01.S03`

Verified the Modelo 840 directory-form registry source through the focused
registry, generic directory-loader, and parser fixture gate.

- Modified: none.
- Created: `.vault/exec/2026-05-27-schema-hardening-m840-standardization/2026-05-27-schema-hardening-m840-standardization-P01-S03.md`

## Description

The first focused pytest invocation used the correct M840 selector but hit
the two-minute command timeout before producing test output. The same scoped
selector was rerun with a longer timeout and completed successfully.

The generated fragment baseline confirms the root-level `840.toml` source
has been eliminated. The largest M840 fragment is now 42 lines, with all
other fragments at or below 28 lines.

## Tests

Passed:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_840_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/adapters/inbound/declaracion/test_parser_boundary.py::test_parser_extracts_modelo_840_synthetic_fixture_targets -q`

Result: 36 passed in 151.12 seconds.
