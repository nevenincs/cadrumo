---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S66'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Record the actual MCP child executable through payload-free runtime telemetry

## Scope

- `src/cadrumo/entrypoints/mcp`

## Description

- Capture the exact first argv element passed to the real supervised subprocess runtime.
- Carry that observed executable through the typed MCP subprocess outcome.
- Hash the executable path into the existing payload-free session telemetry record.
- Preserve the observation for both meta-execute and direct-tool dispatch.

## Outcome

- Every successful MCP-backed CLI call now records a SHA-256 identity for the executable actually supplied to `subprocess.Popen`.
- A complete source MCP oracle produced one identical executable hash for profile creation, work creation, direct calculation, and observation retrieval.
- Observed executable SHA-256: `2921519a67f955270749b6876b5df1ed72d21df40e6106fd303c92db970b7ee5`.
- Ruff and ty passed; sixteen focused runtime, serving-gate, and telemetry tests passed.

## Notes

- Telemetry retains only the one-way executable hash, not the local path or any taxpayer payload.
