---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P09.S20` execution record

Add PartSpec configurations and fetch Renta Part 2 PDFs and manifests for 2020-2024 in `src/aeat/domain/manuals/_fetch.py`.

## Action

Modified `_fetch.py` to register `PartSpec` structures for Renta Part 2 (Deducciones Autonómicas) covering years 2020-2024, enabling them in the compiler's retrieval pipeline.

## Verification

Enforced by `test_fetch.py` verifying specs configuration completeness.
