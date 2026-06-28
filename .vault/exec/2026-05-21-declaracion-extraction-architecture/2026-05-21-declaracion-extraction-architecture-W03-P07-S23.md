---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S23'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# `declaracion-extraction-architecture` `W03.P07.S23`

Verification that M130, M111, M115, and M123 still parse and validate unchanged after W03 discovery work.

## Description

Full test suite run after W03 discovery sweep confirmed all numeric-tier modelos remain functional. No registry files were modified during W03.P05/P06/P07 (P06 steps blocked; P07 steps already-satisfied).

Test results:

- `test_committed_registry.py` — 41/41 passed. All 26 registered modelos validate against the registry schema. M130, M111, M115, M123 snapshots load and pass referential integrity checks.
- `test_parser_boundary.py` — 7/7 passed. Includes:
  - M130 round-trip parse: casillas `01`–`19` extracted correctly from synthetic PDF
  - M111 round-trip parse: casillas `01`–`30` extracted correctly
  - M123 2026 and 2023 historical round-trips: both pass
  - M130 real redacted fixture coverage-gap test: confirms expected failure behaviour
- `test_modelo_parity_coverage.py` — 1/1 passed. All 26 modelos valid.

M115 is tested implicitly via the committed registry validator (its snapshot builds and validates). No dedicated M115 parser boundary test exists in the suite, consistent with the existing test structure.

W03 numeric-casilla changes: none applied. The two blocked steps (S19, S20) require prerequisite registry restructuring. Steps S21, S22 were already satisfied before W03 execution began.

## Tests

- `src/aeat/domain/calculations/registry/test_committed_registry.py`: 41/41 passed
- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`: 7/7 passed
- `src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py`: 1/1 passed
