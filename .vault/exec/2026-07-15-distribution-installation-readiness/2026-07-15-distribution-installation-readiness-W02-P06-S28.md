---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:9368fe1b1a517f16288fe64e212157f0dd580a706a3e94fce208568d25fdbf50'
step_id: 'S28'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Align MCPB platform and Python requirements with the command-bearing distribution

## Scope

- `packaging/mcpb/manifest.json`

## Description

- Validate the committed MCPB v0.4 compatibility declaration and UV launcher.
- Compare the manifest requirement with the bundle-local runtime project and
  the command-bearing distribution's Python requirement.
- Inspect a retained MCPB provisioned by the real UV launcher and the bundle's
  installed MCP tax oracle.
- Run the complete real-cohort MCPB archive test module.

## Outcome

- The committed manifest and emitted runtime project both require
  `>=3.13,<3.14`; no unexecuted operating-system or client compatibility row is
  advertised.
- The server contract uses the MCPB UV runtime to execute the bundle-local
  `src/server.py`; the emitted project pins the root, manuals, and official data
  distributions at the cohort version and resolves all three from embedded
  wheels.
- The retained Windows provision created CPython 3.13 through UV, installed the
  exact embedded cohort, and passed the MCP tax oracle with
  `DP200014:00562 == 23000.00` under `modelo-200-cuota-integra`.
- The retained assembly/runtime evidence SHA-256 is
  `d2106e7e227fe876ea5bd2628d26276f15dec51c36f9e97cc004780f889f890c`;
  it binds MCPB SHA-256
  `8615c66cc05441a8b60f82ccef7f5a1374af81dd37890acf03a6341c62f24cd2`
  to source commit `11c82d2f030c1e75d6b34606e3373421c4f5bce5` and the three wheel digests.
- Focused Ruff passed and all eight real-cohort MCPB archive tests passed in
  202.20 seconds.

## Notes

- Retained runtime evidence is under
  `var/distribution-install-readiness/s27-claude/timeout-fix-20260717T001007/mcpb-smoke/run-20260716T221209605234Z`.
- This step approves only the truthful runtime-requirement declaration. MCPB
  signing, cohort binding, and per-client installation remain S29 and S30.
- The English-only client descriptions remain noncompliant under S68 and are
  not approved by this requirement check.
