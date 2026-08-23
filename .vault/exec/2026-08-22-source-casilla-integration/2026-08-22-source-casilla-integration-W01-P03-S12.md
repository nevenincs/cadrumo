---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:55db1909ed10ad1a82af809fcf3e6931246b3d37865ef2e0c657bdc76f2d78fa'
step_id: 'S12'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# enumerate supported CLI and worksheet ingress surfaces

## Scope

- `dev/source_connectivity/discovery.py`

## Description

- Parse Typer command decorators together with their declared execution policies.
- Enrol policy-declared write commands as supported operator ingress surfaces.
- Distinguish worksheet pull/compute ingress structurally from ordinary CLI ingress.

## Outcome

The source census can now see supported CLI and worksheet ingress without maintaining a command-name allowlist. Each row carries its callback, command group, command token, execution policy, channel, and source locator.

## Notes

Ruff passed. The live scan found inventory create and movement-add ingress and independently identified the Google calculation pull and compute callbacks as worksheet ingress. This is capability evidence only; a write policy does not imply calculation connectivity.
