---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P02.S04` execution record

Backfill missing years/parts for IVA manual PDFs and metadata under `src/aeat/_data/corpus/manuals/iva/`.

## Action

Backfilled official AEAT IVA 2025 PDF manual and its verified manifest under `src/aeat/_data/corpus/manuals/iva/2025/`.

## Verification

Listed manuals via `aeat app registry manuals list` and confirmed that IVA parts for 2020 through 2025 are recognized.
