---
tags:
  - '#exec'
  - '#google-auth-ux'
date: '2026-04-21'
modified: '2026-04-21'
related:
  - '[[2026-04-21-google-auth-ux-phase-1-plan]]'
---

# `google-auth-ux` `phase-1` summary

Completed the first implementation pass of the accepted Google auth UX contract and added explicit verification evidence for the runtime and operator surfaces.

- Modified: `src/aeat/entrypoints/cli/auth.py`
- Created: `.vault/exec/2026-04-21-google-auth-ux-phase-1-step-1.md`

## Description

The repo now presents one guided auth entrypoint for Kent and two named operator paths. The shared auth-path resolver is used by the credential loader, the MCP launcher, and the doctor, so the repo no longer silently prefers service accounts when both path families are present.

The doctor output now distinguishes auth-material readiness from later Drive-backed bootstrap success. During live verification, the workstation surfaced a real local auth-state problem: the Desktop OAuth CLI token and MCP credentials are not currently in a usable state in this worktree. That operational state is now detected and reported honestly, with a concrete `aeat auth init --path desktop-oauth-local-dev` repair path instead of a misleading green summary.

The user-facing guidance and compatibility wrappers were updated to match the runtime. `aeat oauth-client init` remains available as the low-level Desktop OAuth helper, but `aeat auth init` is now the Kent-facing path selection and preparation command.

## Tests

Local verification passed for the focused auth UX suite, `ruff`, `ty`, and docs hooks. Manual command checks also passed for `aeat auth --help`, `aeat auth init --path desktop-oauth-local-dev --no-doctor`, and `python -m aeat.entrypoints.mcp.launch_google_workspace --dump-launch-spec`.
