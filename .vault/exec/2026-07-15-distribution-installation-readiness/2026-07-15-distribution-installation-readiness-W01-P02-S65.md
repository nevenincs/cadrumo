---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S65'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Record invoked CLI origin source snapshot artifact digests and an automatic cohort gate

## Scope

- `dev/packaging/installed_mcp_oracle.py`
- `dev/packaging/tests/test_installed_oracles.py`
- `.github/workflows/packaging-smoke.yml`
- `pyproject.toml`

## Description

- Resolve one exact source commit before extraction and archive that immutable revision.
- Hash all three built wheels and bind installed direct URLs to those exact digests.
- Read the MCP session telemetry and require every supervised child process to attest the cohort's installed `aeat` executable.
- Retain the immutable source identity, wheel digests, CLI oracle evidence, MCP oracle evidence, and observed child executable digest in one durable JSON record.
- Add the installed cohort module to pytest's configured test paths so the serial integration lane collects it automatically.
- Run the installed cohort oracle in packaging CI and upload its retained evidence even when a later packaging step fails.

## Outcome

- Source commit `107f64f72daa9dc2a932e55b092120e0ae2a982d` built and passed as one installed cohort.
- Root wheel SHA-256: `c61891d2b128a20d7b3d17303402621e3c4a65a22440be052892999abd7f9c1c`.
- Manuals wheel SHA-256: `01afebcfc84fb4faf3583c299b2941242291815f021ba0b9482e310c30da8cf5`.
- Official-data wheel SHA-256: `ff46b27b758b8318c858d6e276a90d5430861047687275ab2b2def23b1a19e57`.
- Observed installed `aeat` executable-path SHA-256: `75e82c24611a808713412d153b505e15a6f717a9bef05ab85d268e412bf57d51`.
- Durable evidence: `var/distribution-install-readiness/installed-cohorts/107f64f72daa9dc2a932e55b092120e0ae2a982d/evidence.json`.
- Both installed cohort tests passed in 339.48 seconds, including the direct and MCP grounded tax oracles.
- The configured `integration and serial` collection includes both installed cohort tests without an explicit test path.
- The packaging-smoke workflow owns a dedicated installed-cohort gate and retains its JSON evidence as a CI artifact for 14 days.

## Notes

- The child executable digest is emitted by the production subprocess supervisor for the exact `argv[0]` it invokes; the oracle requires the same digest for profile creation, work creation, calculation, and observation retrieval.
