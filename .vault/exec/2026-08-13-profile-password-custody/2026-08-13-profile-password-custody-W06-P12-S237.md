---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:345246263bd19cb35343cc5e588bb582ca23cc6c9c541551206c6ecda638d1da'
step_id: 'S237'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Remove the retired cadrumo agent-extra installation claim from live harness docstrings and install hints while preserving the sibling cadrumo-harness distribution boundary

## Scope

- `src/cadrumo-harness/src/cadrumo_harness/`

## Description

- Replaced stale optional-extra prose across the live harness MCP modules with the sibling `cadrumo-harness` distribution authority.
- Replaced the missing-runtime and cohort-mismatch hints with `cadrumo-harness` installation and `cadrumo-mcp` launch guidance.
- Strengthened the real refusal tests to assert the complete emitted missing-runtime hint and the version-bound harness cohort hint.
- Searched production, documentation, and tests for the retired phrase and retained only historical ADR and explicit retirement-gate references outside the owned package.

## Outcome

Live harness Python contains no `cadrumo[agent]`, `agent extra`, or `agent-extra` claim. The only install authority emitted by the MCP server names the sibling `cadrumo-harness` distribution, and the real console-script cohort refusal names its exact required harness version.

## Notes

The focused refusal module passed 2 tests and path-scoped Ruff passed. The full harness integration run passed 320 tests and failed 2 unrelated warm-runtime profile-provision tests because their non-interactive create call does not provide the newly mandatory recovery secret channel; 17 serial tests were also explicitly held by the repository marker hook under xdist. Path-scoped ty retains two pre-existing fallback-import diagnostics in `_harness_tools.py`, unrelated to textual install-authority changes.
