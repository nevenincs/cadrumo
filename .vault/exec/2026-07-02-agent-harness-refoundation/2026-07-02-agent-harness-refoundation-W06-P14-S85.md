---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S85'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Author the mcpb Desktop Extension manifest

## Scope

- `packaging/mcpb/manifest.json`

## Description

- Author packaging/mcpb/manifest.json — the Desktop Extension manifest (manifest_version 0.2): server type binary, command aeat-mcp (stdio), a persona user_config, the advertised tool summary, and the on-host/never-file-to-AEAT posture in the description. Points at the aeat-mcp console script, which requires the aeat[agent] extra installed on-host beside the encrypted store.

## Outcome

Built and verified: `python packaging/mcpb/build.py --check` validates;
a real build produces `dist/aeat.mcpb` (honestly UNSIGNED on this host — no
signing identity). 4 packaging tests pass. Ruff clean.

## Notes

The repo-root `packaging/` name collides with the installed PyPA
`packaging` library, so the build tool is a SCRIPT, not an importable
package; the test loads it by file path. Signing is the operator's release
step, deliberately not faked at build time.
