---
tags:
  - '#reference'
  - '#desktop-shell'
date: '2026-11-15'
modified: '2026-11-15'
body_schema: 'body-v2'
body_hash: 'sha256:7f6e60922527c2be69cadc2a288850fb6fa65808b67f7c11c8e3e68dba805d25'
related: []
---
# `desktop-shell` reference: `Desktop console environment and agent provisioning seams`

## Summary

How the desktop console starts today and where the agent service's provisioning lives, read on 2026-11-15 from lane/desktop and the cadrumo-agent checkout.

## Console spawn

- `native/desktop/src-tauri/src/terminal/mod.rs:56-93`: `Program::for_kind` runs the `console` kind as a plain shell PTY; `python` and `tui` kinds run their pinned programs.
- `native/desktop/src-tauri/src/terminal/session.rs:231-241`: the child calls `env_clear` and receives only a filtered snapshot of the desktop's environment; the working directory is the shared console workspace.
- `native/desktop/src-tauri/src/environment.rs:174-266`: the filter clears `PYTHON*`, `CADRUMO_*` (pins excepted), `AEAT_*` and `FINANCIAL_*`.
- `native/platform/src/storage.rs:557-600`: the shared console workspace path.
- No per-profile environment store exists in the host, the agent service or the runtime; nothing re-reads the console environment on sign-in, sign-out or profile change.

## Agent provisioning

- cadrumo-agent `src/cadrumo_agent/providers/_hosted_provider_home.py:18-36` and `providers/_native_role.py:109`: provider homes (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`) where provider sign-in keeps its credentials.
- cadrumo-agent `src/cadrumo_agent/harness/workspace.py:244`: `materialise_workspace` writes skills, rules and `CLAUDE.md`/`AGENTS.md`; reachable only through `python -m cadrumo_agent.harness` (`harness/__main__.py:21`).
- `src/cadrumo_agent_service/host/launch_environment.py:276-342`: the service builds the gateway's environment, including the `cadrumo-mcp` registration, and gives it to the gateway alone.
- `src/cadrumo_agent_service/service_administration.py`: the authenticated administration channel where a new read would live.

## Gaps against the operator order

The console carries no provider home, no harness workspace, no tool server registration and no refresh. Provider command-line programs started there therefore run outside the profile's provider sign-in, skills and tools.
