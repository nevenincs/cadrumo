---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-17'
step_id: 'S22'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Prove Homebrew resources hashes Python requirement commands and test block match the cohort

## Scope

- `packaging/homebrew/tests/test_generate.py`

## Description

- Build the real root and companion source distributions.
- Generate the formula twice and compare its bytes.
- Verify root and companion identities, hashes, exact dependency resources, Python requirement, both command paths, and the test block.
- Exercise rejection of renamed foreign companions and mutable release URLs.

## Outcome

- Six real-artifact integration tests passed.
- The tests exposed and repaired the macOS-arm64 `greenlet` marker split instead of widening the resource to an unsupported platform.

## Notes

- No Homebrew binary or hosted runner was used; S23 and S24 remain open.
