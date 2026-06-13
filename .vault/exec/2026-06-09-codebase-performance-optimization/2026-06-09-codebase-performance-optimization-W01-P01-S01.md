---
tags:
  - '#exec'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S01'
related:
  - "[[2026-06-09-codebase-performance-optimization-plan]]"
---




# Include user_profile/schema.toml in registry tree fingerprints

## Scope

- `src/aeat/domain/calculations/registry/_loader.py`

## Description

- Include `user_profile/schema.toml` file fingerprint in the registry fingerprint list.

## Outcome

- Done. Schema modifications now invalidate the registry fingerprint and validation cache.

## Notes

