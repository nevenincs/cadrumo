---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
step_id: 'S39'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update the Docker clean-install probe to Cadrumo names

## Scope

- `dev/packaging/smoke_docker.py`

## Description

- Read the binding naming ADR and confirm that the Docker probe must invoke the
  sole human executable `aeat` while requiring `CADRUMO` from its version
  identity output.
- Correct the generated core probe's case-sensitive installed-version
  assertion without changing product machine identifiers or authority names.
- Run lint, formatting, focused real Docker-selection tests, and the complete
  clean Linux Docker packaging smoke.

## Outcome

The Docker core probe now rejects installed `aeat --version` output that does
not contain the `CADRUMO` identity. Four focused integration tests passed,
including the configured WSL Docker CLI and daemon preflight. The full Docker
smoke built `cadrumo-0.2.0-py3-none-any.whl`, installed it inside a fresh Linux
container, exercised the generated core probe, and wrote its smoke manifest.

## Notes

- The real Docker smoke passed in 77.1 seconds through the configured
  `wsl:Ubuntu` backend; no environment waiver was required.
- `registry/aeat`, `corpus/aeat_official`, the authority adapter namespace, and
  authority-owned `AEAT_*` settings remain intentionally unchanged.
- Sentence prose casing was outside this Step; uppercase is required here
  because version output is an identity context under the binding ADR.
