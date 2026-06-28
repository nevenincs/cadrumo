---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S327'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---




# W12.P26.S327 registry plaintext exception

## Scope

- `src/aeat/domain/calculations/registry/_parity_tapes.py`

## Description

- Audited `domain.calculations.registry._parity_tapes` against the target `plaintext-exception` (owner `W12.P24.S96`).
- Confirmed the module defines parity-test tape types for the workbook-parity / fichero-BOE oracle replay surface; tapes are read from bundled package data and consumed by the parity gates in the test surface.
- The `plain-file` signal is by-design: parity tapes are authored test artefacts and ship with the package; the loader writes nothing.

## Outcome

- AFR-225 closed: justified plaintext exception (bundled parity-tape oracle artefacts). No source change required.

## Notes

- Audit-only Step.
