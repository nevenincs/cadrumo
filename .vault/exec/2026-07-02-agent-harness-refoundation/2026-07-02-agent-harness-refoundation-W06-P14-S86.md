---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:be64d1adc8558cf20bdf8393eb59e1ac95c6c7227e25b04fb7994d576a8a5513'
step_id: 'S86'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add the mcpb build-and-sign script behind the agent extra

## Scope

- `packaging/mcpb/build.py`

## Description

- Author packaging/mcpb/build.py + test_build.py — validates the manifest against a required-field contract, stages it, and zips dist/aeat.mcpb (gitignored build output). Signing is HONEST: signs only when the mcpb CLI + a real identity are present; otherwise emits an UNSIGNED bundle and says so — never fabricates a signature. 4 real-behavior tests pass.

## Outcome

Built and verified: `python packaging/mcpb/build.py --check` validates;
a real build produces `dist/aeat.mcpb` (honestly UNSIGNED on this host — no
signing identity). 4 packaging tests pass. Ruff clean.

## Notes

The repo-root `packaging/` name collides with the installed PyPA
`packaging` library, so the build tool is a SCRIPT, not an importable
package; the test loads it by file path. Signing is the operator's release
step, deliberately not faked at build time.
