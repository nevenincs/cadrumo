---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:0de1aa87d14a1f111574668a8912923f7cd0d22f3fc76b01d0129db42dfa7572'
step_id: 'S11'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite the derived-output validator to iterate the taxonomy instead of the dict while keeping the model-fields-set skip, gated by the existing explicit-override-wins test staying green

## Scope

- `src/cadrumo/core/config.py`

## Description

- Rewrite the derived-output validator to iterate `ROOT_DERIVED_STORAGE_LOCATIONS` from the taxonomy instead of the shipped dict, keeping the `model_fields_set` skip.

## Outcome

Landed in commit `ceaee35e78` ("derive settings paths and the override rebuild from the taxonomy"). Gated by the existing `test_explicit_output_dir_override_wins_over_derivation`, kept green.

## Notes
