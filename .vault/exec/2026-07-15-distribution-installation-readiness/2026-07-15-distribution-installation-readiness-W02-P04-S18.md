---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S18'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Prove Scoop generation matches the cohort and exposes both installed commands

## Scope

- `packaging/scoop/tests/test_generate.py`

## Description

- Build the real command wheel and both mandatory companion wheels once.
- Generate the Scoop manifest twice and require byte-identical output.
- Match every generated release URL and digest to the supplied cohort.
- Pin the exact pre-install lifecycle, dependency check, persistent state, command wrappers, quoting, and argument forwarding.
- Reject incomplete, duplicate, renamed, mixed-version, conditionally pinned, or mutably addressed cohorts.

## Outcome

- Seven real-artifact tests pass in 63.75 seconds.
- The accepted manifest exposes both Scoop command aliases and creates their wrapper targets before Scoop shim creation.
- Negative cases prove the generator fails closed for malformed cohort membership, metadata, version, dependency, and acquisition URL inputs.
- Ruff and ty pass for the Scoop generator test surface.

## Notes

- S19 owns native Scoop bucket installation, update, persistence, CLI, and MCP acceptance.
- S20 owns continuous execution of this test on the declared Windows release row.
