---
tags:
  - '#exec'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-07-17'
body_hash: 'sha256:6c6c56fe7098943ddd3c83292db0b4dca6abb7b2c0a33b57c4a5e89f76571260'
step_id: 'S02'
related:
  - "[[2026-06-09-codebase-performance-optimization-plan]]"
---

# Implement validation cache file checking and writing in _load_authority

## Scope

- `src/aeat/domain/calculations/registry/_authority.py`

## Description

- Implement validated cache logic in `_load_authority` using SHA-256 fingerprint hash check.

## Outcome

- Done. Speeds up subsequent loads by bypassing the slow `validate_registry` call.

## Notes
