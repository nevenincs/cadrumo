---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:2fa3cce6fe885d6099c08bd693e08e681f6dd53c420060f0f3b2e641749314a8'
step_id: 'S19'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Remove the config profile sandbox use registration and execution path without an alias

## Scope

- `src/cadrumo/entrypoints/cli/_config/_sandbox.py`

## Description

- Delete `_register_sandbox_use_command` and its registration from `_sandbox.py` with no alias (no-legacy hard cut).
- Delete the `ConfigProfileSandboxUseResult` schema and its `config.profile.sandbox.use` registration from `_config_sandbox_payloads.py`.
- Remove `config.profile.sandbox.use` from the operator-surface `_risk_table.py` and from the MCP `_identity_gate.py` active-identity-changing set; correct the two docstrings naming the removed door (`_common.py`, `_identity_gate.py`).

## Outcome

The second sandbox-selection door is gone across code, JSON schema, risk metadata, and the MCP identity gate; `switch` (S18) is the sole selector. Sandbox-CLI suite green (44 passed); schema-conformance, custody-lifecycle, and MCP suites green (420 passed); operator-surface risk suite green (56 passed). Locale keys for the removed verb are dropped in S28 through the locales CLI.

## Notes

Sandbox entry is now `config switch sandbox:<name>` (canonical label) — the removed `use` had no independent authority, delegating to the same select-lifecycle-span primitive `switch` uses.
