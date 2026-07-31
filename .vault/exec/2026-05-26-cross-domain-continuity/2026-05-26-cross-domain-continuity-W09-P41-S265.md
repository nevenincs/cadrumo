---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:6a7a3700c76e4d96d0eae2543a53c278fd15d9513db30ce50b20e1ec7df44388'
step_id: 'S265'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# FU-W08-C drop unsecured-backend AEAT_SECRET_STORE_BACKEND=unsecured and AEAT_ALLOW_UNENCRYPTED=1 monkeypatches from _isolated_state autouse fixture in test_output_language_parity.py

## Scope

- `--help never reaches storage so these env-vars serve no purpose`
- `src/aeat/entrypoints/cli/test_output_language_parity.py`

## Description

- Reconciles the checked historical S265 row against the direct evidence named in the related reconciliation audit.
- Adds no production-source change.

## Outcome

- Restores the one-Step/one-record traceability edge for this historical checked row.
- The related audit names the exact supporting audit, execution record, or commit evidence.

## Notes

- This record asserts no new implementation or re-run verification; it records evidence reconciliation only.
