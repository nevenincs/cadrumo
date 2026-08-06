---
tags:
  - '#exec'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-07-17'
body_hash: 'sha256:3e2c222ab7b09d8c802ed05f349548bf139c6e19c3a23138beafb92edd46c011'
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
