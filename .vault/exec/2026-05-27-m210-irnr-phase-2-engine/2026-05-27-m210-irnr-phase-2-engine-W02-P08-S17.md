---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:4555affd743108d156672f22c952ca660170e55559bbc253f0c00d9748edc98c'
step_id: 'S17'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# Localize the accepted M210 source-ingestion issue reasons through the locale CLI and route calculate-time diagnostics through the canonical translation surface

## Scope

- `src/aeat/locales + src/aeat/application/aggregation`

## Description

- Add M210 source-classification diagnostics, source-mode errors, and CLI option help through `aeat.locales`.
- Route the aggregation and calculation errors through the canonical `tr()` translation surface.
- Preserve the four supported catalogue translations while staging only M210 keys from the shared worktree.

## Outcome

`ca`, `en`, `es`, and `hu` locale scaffold and audit both pass. The CLI exposes localized M210 ledger-classification and gross-income-source help. Landed in `8f5f690ed0`.

## Notes

Unrelated catalogue changes remained unstaged and are not part of this delivery.
