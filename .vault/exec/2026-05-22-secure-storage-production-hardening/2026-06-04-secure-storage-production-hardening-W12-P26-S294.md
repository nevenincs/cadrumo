---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S294'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s294-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S294`

Closed `AFR-192` for the application error-registry manifest-discovery slice.

## Description

- Register modelo projection and comparison exceptions with stable `ErrorCode` metadata.
- Register modelo work-selector and calculation-revision-selector exceptions.
- Register modelo work-addressing exceptions and enroll their classes under the modelo `AeatError` hierarchy.
- Sync the corresponding locale leaves through the canonical locale CLI.

## Outcome

`AFR-192` is closed. The central registry now covers the modelo split-out command/application errors exercised by the projection, selector, natural-key, and registry-enforcement tests.

## Notes

This was a cross-cutting repair discovered while validating locale scanner work. The commit also carries the split-out modelo modules needed by the registry rows; pushing only the registry would leave the branch with declared codes for modules absent from the tree.
