---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:d020af7c15e17f0b89ab21341cfbbc51f9464dc4a3acfa444d9134cf059647dd'
step_id: 'S494'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Reconstruct or reopen evidence for W20.P40.S461 before plan closure

## Scope

- `src/aeat/entrypoints/cli/_config`

## Description

- Inspected the accepted D1 command-surface decision and landing commit `f2e1b0c5ef`.
- Verified that the commit hard-replaced `aeat config unlock NAME` with `aeat config switch NAME` without an alias or compatibility shadow.
- Exercised the installed CLI: `aeat config unlock --help` fails with Click's no-command result and `aeat config switch --help` resolves successfully.
- Reconciled the historic S461 claim through W22 P44 records rather than reintroducing the retired command.

## Outcome

The W20 custody-contract result is present in code, tests, localized operator guidance, and the accepted D1 decision. The missing historical execution record was an evidence gap only: the current reconstruction proves the intended hard replacement and records the actual implementation commit. No production change or deferred compatibility work remains.

## Notes

The original S461 was checked without an execution record. W22 P44 separately corrected stale planning and rollout language so this reconstruction is aligned with the code-led contract.
