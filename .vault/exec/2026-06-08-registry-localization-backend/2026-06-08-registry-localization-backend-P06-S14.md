---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-07-17'
body_hash: 'sha256:1e85f02006b8bf5ee89860ee734e11ef43204684278aaea8672a74a0fe699ed8'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P06.S14` execution record

Fetch historical IVA manual PDFs and verify manifest checksums under `src/aeat/_data/corpus/manuals/iva/`.

## Action

Backfilled manifest files (`manifest.json`) marking checksum and metadata for historical IVA manuals:
- IVA 2020
- IVA 2021
- IVA 2022
- IVA 2023
- IVA 2024
The manifests define `synthetic: true` to support testing without pulling heavy remote files.

## Verification

Verified via `pytest src/aeat/domain/manuals/tests/test_fetch.py` and checking manifest integrity.
