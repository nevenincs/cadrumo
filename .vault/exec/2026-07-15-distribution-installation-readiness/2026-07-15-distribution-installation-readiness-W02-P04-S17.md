---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S17'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Generate a versioned Scoop manifest with immutable cohort URLs hashes persistence and both command shims

## Scope

- `packaging/scoop/generate.py`

## Description

- Discover and validate exactly one command wheel and both mandatory companion wheels.
- Require one version across the cohort and exact root dependency pins to both companions.
- Bind immutable GitHub release URLs to the real artifact filenames and SHA-256 digests.
- Install the complete local cohort into one Scoop-owned virtual environment.
- Generate durable `aeat` and `cadrumo-mcp` command shims whose state root survives Scoop updates.

## Outcome

- The generator emitted a deterministic versioned Scoop manifest from the supplied `0.2.1` cohort.
- A local simulation executed the generated `post_install` commands, installed 72 resolved packages from the exact three local wheels, and passed `uv pip check`.
- Both generated command wrappers executed from the simulated Scoop installation.
- The installed `aeat` wrapper completed the grounded Modelo 200 oracle with `DP200014:00562=23000.00` and persisted revision `603cf788992642cc4eb10593bd994a643ba0c15710444042a4d058d40ea1f909`.
- Ruff and ty passed for the generator.

## Notes

- Full bucket acquisition, update, removal, and persistence acceptance remain owned by S19 and S20.
- Generated local evidence is retained beneath `var/distribution-install-readiness/s17-scoop`.
