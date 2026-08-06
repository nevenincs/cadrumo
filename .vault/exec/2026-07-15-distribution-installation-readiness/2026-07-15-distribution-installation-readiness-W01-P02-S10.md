---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:a068818f041aa0c78829d07f759bcb124b41676738a2b337d31780016d7c9d73'
step_id: 'S10'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Prove both installed commands originate from one environment and one cohort

## Scope

- `dev/packaging/tests/test_installed_oracles.py`

## Description

- Build the command wheel and both mandatory companion wheels once from committed `HEAD`.
- Install that exact local cohort once with the `agent` extra.
- Read installed distribution metadata, console-script declarations, direct artifact URLs, and
  installer-recorded SHA-256 values through the installed interpreter.
- Run both the direct CLI and MCP grounded Modelo 200 oracles from that one environment.

## Outcome

- `aeat` and `cadrumo-mcp` resolved to the same installed scripts directory.
- The three installed distributions shared one site-packages root and one version.
- Root metadata retained both exact-version mandatory companion requirements.
- The installed direct URLs and SHA-256 values matched the three wheels built for the test.
- Both transports independently produced `DP200014:00562=23000.00` with identical formula,
  legal references, source references, and permitted notice codes.
- Ruff, ty, Python compilation, and both real serial integration tests passed.

## Notes

- The complete cohort-bound run took 517.26 seconds.
- The test installs once and then executes both oracles, preventing independently passing
  evidence from silently referring to different environments or rebuilt wheels.
