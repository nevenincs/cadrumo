---
tags:
  - '#exec'
  - '#google-auth-ux'
date: '2026-04-21'
modified: '2026-04-21'
related:
  - '[[2026-04-21-google-auth-ux-phase-1-plan]]'
---

# `google-auth-ux` `phase-1` `step-1`

Implemented the Kent-facing Google auth UX scaffold across the CLI, resolver, MCP launcher, diagnostics, and user-facing guidance.

- Modified: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`
- Created: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_google_paths.py`

## Description

Added one shared Google auth inspection model that resolves the active path deterministically, blocks ambiguous dual-path state, and exposes the local Desktop OAuth, service-account, CLI token, MCP cache, and ADC surfaces to the rest of the repo.

Added the guided `aeat auth init` entrypoint in `src/aeat/entrypoints/cli/auth.py` and wired it into `src/aeat/entrypoints/cli/__init__.py`. The command now sets `GOOGLE_AUTH_PATH`, imports Desktop OAuth or service-account JSON input into repo-local gitignored paths, prepares the MCP cache directory, supports explicit CLI token reset for stale-scope recovery, and emits Kent-facing purpose/action/source/browser/success/next-step messages.

Updated `src/aeat/entrypoints/cli/doctor.py` so it reports the active path, auth-material readiness, MCP cache readiness, inactive-path drift, and Desktop OAuth Drive-scope failure truthfully. The doctor now points the operator at `aeat auth init --path desktop-oauth-local-dev --reset-cli-token` when the cached Desktop OAuth token is stale enough to break Drive-backed bootstrap work.

Aligned the MCP launch contract in `src/aeat/entrypoints/mcp/launch_google_workspace.py`, the settings surface in `src/aeat/config.py`, the compatibility wrappers in `justfile`, and the user-facing guidance in `README.md`, `CONTRIBUTING.md`, and `env/.env.example` with the accepted two-path contract.

## Tests

Verification covered `src/aeat/_test_auth.py`, `src/aeat/entrypoints/cli/_test_auth.py`, `src/aeat/entrypoints/cli/_test_doctor.py`, `src/aeat/entrypoints/cli/_test_oauth.py`, `src/aeat/entrypoints/mcp/test_launch_google_workspace.py`, and `tests/test_config.py`, plus `ruff`, `ty`, and focused docs hooks.
