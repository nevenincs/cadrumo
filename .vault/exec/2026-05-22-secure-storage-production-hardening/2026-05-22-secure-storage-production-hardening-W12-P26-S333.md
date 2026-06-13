---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S333'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---




# W12.P26.S333 registry audit close

## Scope

- `src/aeat/domain/calculations/registry/_workbook_parity.py`

## Description

- Audited `domain.calculations.registry._workbook_parity` against the target `plaintext-exception` (owner `W12.P24.S96`).
- Confirmed the module defines the workbook-parity record types consumed by the LibreOffice parity gate; the workbook-parity oracle ships as bundled package data and is read at parity-test time only (gated by the `workbook_parity` pytest marker).
- The `plain-file` signal is by-design: parity tapes / workbook fixtures are bundled artefacts; the parity gate writes nothing, only compares engine output against the recorded oracle.

## Outcome

- AFR-231 closed: justified plaintext exception (bundled workbook-parity oracle data). No source change required.

## Notes

- Audit-only Step.
