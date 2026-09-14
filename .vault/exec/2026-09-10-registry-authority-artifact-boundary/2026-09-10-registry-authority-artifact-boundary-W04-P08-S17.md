---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-13'
modified: '2026-09-13'
body_schema: 'body-v2'
body_hash: 'sha256:743b6c0a05793cb827f7625e83696a28312d4b7d6bfc27f26feae874907d6fde'
step_id: 'S17'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---

# Prove installed artifact-only execution, corruption refusal, zero raw AEAT readers, typed operative-value consumption and centralized temporal admission

## Scope

- `tests/integration/`
- `dev/packaging/tests/`
- `src/cadrumo/tests/`

## Changes

- `M` `dev/packaging/installed_mcp_oracle.py`
- `M` `dev/packaging/installed_tax_oracle.py`
- `M` `dev/packaging/tests/test_installed_oracles.py`
- `A` `dev/packaging/tests/test_installed_mcp_oracle_stderr.py`
- `M` `src/cadrumo/entrypoints/cli/_command_runtime.py`
- `M` `src/cadrumo/entrypoints/cli/config/profile_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/config/tests/test_config_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_command_runtime.py`
- `A` `src/cadrumo_harness/mcp/_cli_executable.py`
- `M` `src/cadrumo_harness/mcp/command_surface.py`
- `M` `src/cadrumo_harness/mcp/inprocess.py`
- `M` `src/cadrumo_harness/mcp/server.py`
- `A` `src/cadrumo_harness/mcp/tests/test_cli_executable.py`
- `A` `src/cadrumo_harness/mcp/tests/test_server_profile_secret_composition.py`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "" --timeout=1800 <S17 exact-wheel selection>` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "" dev/packaging/tests/test_authority_runtime_boundary.py` -> `pass`
