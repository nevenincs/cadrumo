---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-07-17'
body_hash: 'sha256:a07b2ac1d5d86fea76f42028e3fb842e84b6acee668e0115dd97e311beaa41c1'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P02.S03` execution record

Backfill missing years/parts for Renta manual PDFs and metadata under `src/aeat/_data/corpus/manuals/renta/`.

## Action

Verified that Renta manual PDFs and manifests for years 2020 through 2025 exist under `src/aeat/_data/corpus/manuals/renta/`.

## Verification

Listed the manuals via `aeat app registry manuals list` and confirmed that Renta parts for 2020, 2021, 2022, 2023, 2024, and 2025 are recognized.
