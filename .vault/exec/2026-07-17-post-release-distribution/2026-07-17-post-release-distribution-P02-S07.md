---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:4f15eb3e9c176f220442751526d8fb6204055ebf6a11f86512e7353bd2ad69bf'
step_id: 'S07'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# DONE, macOS Python row green in run 29657832151 after root-causing the deterministic per-binary Keychain hang via the worker-stack capture (custody file-backend pin b5e6780fb1, product follow-up issue 615)

## Scope

- `.github/workflows/packaging-smoke.yml`

## Description

- Run the cohort-bound installed-behavior oracle on the claimed macOS Python row in real CI.
- Root-cause and fix the deterministic per-binary Keychain hang blocking the macOS leg.

## Outcome

The macOS Python row is green in the same run `29657832151` (commit `1abbc48c72`, in HEAD) after root-causing the deterministic per-binary Keychain hang via the worker-stack capture and pinning the custody file backend at commit `b5e6780fb1` (in HEAD). The residual macOS-native custody concern is tracked as product follow-up issue `615`. Closed against a real green CI run.

## Notes

Retroactive execution record; step already checked. The custody file-backend pin is an accepted mitigation with a named product follow-up, not a silenced failure. Vault-only bookkeeping.
