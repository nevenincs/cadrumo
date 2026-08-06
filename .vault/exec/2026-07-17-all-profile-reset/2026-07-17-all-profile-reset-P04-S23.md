---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-24'
modified: '2026-07-25'
body_hash: 'sha256:e4e0b8587b761f16e8c27fbd5223b6672c05eb39a167d1615f06b0e8cce8d74e'
step_id: 'S23'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Prove switching and strong logout through real persisted custody state

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`

## Description

- Create a real encrypted profile through the public command surface.
- Execute strong profile logout in a fresh process and prove the retired root lock command is unavailable.
- Re-select the same profile by exact label and again through the default pointer path.

## Outcome

Switching and strong logout are proven against real persisted custody state, with no duplicate command door surviving for either operation. The focused integration module is present at HEAD and carries the proof.

## Notes

This step is a carried-forward row. The work landed under the originating campaign as its own step, whose execution record is preserved under that campaign's execution folder and states a six-test pass in roughly 186 seconds. The rescope record that split the originating campaign into this plan documents the carry explicitly and names the attribution, so the evidence was never missing; it was recorded under the originating stem.

This record is authored under the successor stem as well, on 2026-07-24, for two reasons. First, it was the only step in this plan that a plan-status run still reported as lacking an execution record, and the plan-closure discipline permits exactly two states: a record, or a documented deferral. Second, the originating campaign is a candidate for archival, and an archive relocates the originating execution folder; a successor step whose only evidence lives in the archived tree would lose its live answer. Recording it here makes this plan self-sufficient against that move.

The underlying test module carries later commits from adjacent custody work, so the module at HEAD is broader than the row this record covers. This record is a retroactive reconstruction from the originating record and the tree at HEAD, not a contemporaneous log.
