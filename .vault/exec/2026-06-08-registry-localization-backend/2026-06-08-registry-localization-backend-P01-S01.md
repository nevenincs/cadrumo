---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-07-17'
body_hash: 'sha256:85c1b80c24f230e0ecfa4b604c9b7b58a75a262d271efef527352d6a6c96f671'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P01.S01` execution record

Research schema structures and localization files under `src/aeat/domain/calculations/registry/`.

## Action

Researched the existing Casper/registry compile and load phases to determine where and how to integrate localization assets.

## Verification

Confirmed the placement of local translation files without polluting the core Python localization package or bypassing the registry snapshots compilation.
