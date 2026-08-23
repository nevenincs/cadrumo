---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:39d7350f06bdc318d5de314f3966a6ca1e90a57bc4225305acb78596cf2b7da9'
step_id: 'S24'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# implement census generation and comparison commands

## Scope

- `dev/source_connectivity/cli.py`

## Description

- Add a read-only developer CLI over independent source-capability discovery.
- Emit stable sorted discovery JSON through the `generate` command.
- Compare live capability identities with the canonical reviewed census through the `compare` command.
- Return a gating nonzero exit when census assignment or selector digest validation fails.

## Outcome

Maintainers can inspect the live 428-capability discovery inventory and compare it with the 14-row
reviewed census using one deterministic command surface. The commands do not write the census, so
reviewed classifications remain the sole authority and generated facts cannot overwrite decisions.

## Notes

Ruff, command help, live generation, and live comparison passed. The initial lint run rejected a
function call in a Typer default; the current-working-directory default is now captured once at module
load and lint passes.
