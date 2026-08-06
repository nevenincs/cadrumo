---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:f1bc50d2b6ec5f697ad1ac707dd71a87eb935c5b98b85b1aec85c77bb3213725'
step_id: 'S06'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Prove the definition contract with build-time validator tests covering duplicate ids, non-forward references, literal-copy refusal, and repeating-group shape

## Scope

- `src/cadrumo/application/flows/tests/test_definition.py`

## Description

- Author the definition build-validator suite covering every refusal arm plus positive builds and fingerprint stability/change.
- Land in commit 30e5884352 (15 tests).

## Outcome

All 15 green; reviewer confirmed coverage of every build-time validator.

## Notes

Authored by the dispatched high-executor.
