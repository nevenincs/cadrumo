---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-07-17'
body_hash: 'sha256:bc4d9fe167f6837cd352e0e35ed52156635c470d0702f52bb8ec9c42a329f11f'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P05.S13` execution record

Verify that all years 2020-2024 report structure_available: True under `src/aeat/_data/corpus/manuals/renta/`.

## Action

Queried the Renta manuals via the CLI for years 2020 through 2024.

## Verification

Confirmed via `aeat app registry manuals view` that `structure_available: True` is reported for all years, and ran the manuals domain test suite to assert clean loader validation.
