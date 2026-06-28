---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S383'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s383-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S383`

Closed `AFR-281` for the modelo CLI manifest-discovery slice.

## Description

- Wire modelo work commands through application-level selector and addressing services.
- Add projection/compare command registration through a focused CLI module.
- Preserve localized command help and typed CLI refusal rendering.
- Validate the natural-key workflow through real CLI/profile storage tests.

## Outcome

`AFR-281` is closed. The modelo CLI no longer treats copied ids as the only ergonomic path for calculate/verify/export and now uses typed application selectors for common visible targets.

## Notes

This record covers a cross-commit of already-wired split-out work that intersected the registry hardening. New split-out files still need their own AFR inventory rows in a later register expansion.
