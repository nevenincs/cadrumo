---
tags:
  - '#exec'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-06-09'
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

