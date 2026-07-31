---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:5239030435c1c5062ebf6112276ce193c20728e8d1b2e6b651d5e5b76b39e532'
step_id: 'S06'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Remove EvidenceBundleService replay, its public export, and backend tests while preserving evidence check and unrelated observability replay facilities

## Scope

- `src/cadrumo/application/evidence/_service.py`

## Description

- Remove `EvidenceBundleService.replay` (a thin wrapper that delegated to `check` — a second, weaker path claiming the same integrity contract) and its module/class docstring references to the replay verb.
- Remove the backend replay test `TestReplay.test_replay_never_mutates_bundle_state`.
- Preserve `check` (the verifier) and the unrelated observability parity-tape replay facility.

## Outcome

- The evidence service now exposes only build/verify/export; there is no duplicate replay authority. Landed together with the CLI command removal (S08) and proof (S10) in one green vertical, commit `87f49c5d2f`. Evidence suite 20 passed.

## Notes

- None.
