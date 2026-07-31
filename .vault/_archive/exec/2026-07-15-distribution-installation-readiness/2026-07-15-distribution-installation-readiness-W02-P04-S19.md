---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S19'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Install from the intended bucket in Windows Sandbox and execute CLI MCP update and persistence behavior

## Scope

- `dev/packaging/smoke_scoop.ps1`

## Description

- Stage the generated immutable cohort manifest in a local Git-backed Scoop bucket.
- Install the bucket-qualified package and resolve both command targets from Scoop's application root.
- Require a forced update to replace non-persisted application bytes while retaining persisted state.
- Uninstall without purge, reinstall from the same bucket, and require the persisted marker to remain byte-identical.
- Execute the grounded Modelo 200 oracle through installed `aeat` and the public MCP protocol.
- Purge the staged application, persisted state, transient dependency, and local bucket after evidence is written.

## Outcome

- A fresh Windows 11 AMD64 host run completed in 272.83 seconds with status `passed`.
- Scoop acquired all three `0.2.1` wheels from the bucket manifest and verified their immutable SHA-256 hashes.
- Forced update removed a deliberately non-persisted marker and retained the persisted marker digest `7a95b922526c2ceb72e8f5af911ae3f335095468e1cbad168699d260d7909ba3`.
- Uninstall without purge and bucket-qualified reinstall retained the same marker bytes.
- Installed `aeat` returned `DP200014:00562 == 23000.00` under formula `modelo-200-cuota-integra`, with LIS Article 29 and both authoritative source references.
- Installed `cadrumo-mcp` completed the public protocol calculation with the same target value and grounding.
- Seven real-artifact Scoop generator tests passed in 68.29 seconds, and PowerShell parsing plus diff checks were clean.

## Notes

- Windows Sandbox is not installed on this workstation. This host-mode evidence
  validates the implementation but does not close S19; the Sandbox acceptance
  remains open. The separate hosted Windows release-row execution remains S20.
- Failed exploratory host runs identified and corrected direct-manifest acquisition, command-target assumptions, and missing removal/reinstall proof before the retained passing run.
- Retained diagnostic evidence is under `var/distribution-install-readiness/s19-scoop/final-host-run`.
