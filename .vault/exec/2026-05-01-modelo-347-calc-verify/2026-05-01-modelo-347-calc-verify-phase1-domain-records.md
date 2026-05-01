---
tags:
  - '#exec'
  - '#modelo-347-calc-verify'
date: '2026-05-01'
related:
  - '[[2026-05-01-modelo-347-calc-verify-plan]]'
---

# `modelo-347-calc-verify` `implementation` `phase1-domain-records`

Added strict Modelo 347 per-counterparty records and per-year schema manifests.

- Created: `src/aeat/domain/modelos/m347/__init__.py`
- Created: `src/aeat/domain/modelos/m347/_records.py`
- Created: `src/aeat/domain/modelos/m347/_rules_2024.py`
- Created: `src/aeat/domain/modelos/m347/_rules_2025.py`
- Created: `src/aeat/domain/modelos/m347/_rules_2026.py`
- Created: `src/aeat/domain/modelos/m347/test_records.py`

## Description

`Modelo347RecordLine` is frozen, strict, and extra-forbid. It covers the type-2 declared-person fields needed for M347 Tier-S parity, including the modern cash-accounting, reverse-charge, non-customs-deposit, EU VAT, real-estate quarterly, and BDNS surfaces. The year manifests encode the shared 2024/2025/2026 schema and 3005.06 EUR threshold.

## Tests

Covered strict validation, quarter-to-annual consistency, cash-origin year requirements, blank identity rejection, BOE optional field preservation, and per-year manifest identity.
