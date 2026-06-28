---
tags:
  - '#exec'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-06-09'
related:
  - '[[2026-06-09-codebase-performance-optimization-plan]]'
---

# `codebase-performance-optimization` `W01.P01` summary

Completed Phase 1 of Wave 1, introducing persistent validation caching for the ValidatedRegistryAuthority.

- Modified: `src/aeat/domain/calculations/registry/_loader.py`
- Modified: `src/aeat/domain/calculations/registry/_authority.py`
- Modified: `src/aeat/domain/calculations/registry/tests/test_authority.py`
- Created: `.vault/exec/2026-06-09-codebase-performance-optimization/2026-06-09-codebase-performance-optimization-W01-P01-S01.md`
- Created: `.vault/exec/2026-06-09-codebase-performance-optimization/2026-06-09-codebase-performance-optimization-W01-P01-S02.md`
- Created: `.vault/exec/2026-06-09-codebase-performance-optimization/2026-06-09-codebase-performance-optimization-W01-P01-S03.md`

## Description

The startup resolve time for the registry was optimized by introducing a persistent validation cache. Fingerprints of all registry TOML files (now including the user profile schema) are collected to build a unique SHA-256 hash. If this hash matches an existing validation cache file, the authority skips the expensive `validate_registry` step on boot. This reduces warm registry authority load time from ~3.66s to ~0.7s (excluding Python startup).

## Tests

- Pytest ran successfully on `src/aeat/domain/calculations/registry/tests/test_authority.py` with 7 passed tests in 1.01s.
- `test_authority_uses_validation_cache_and_invalidates` successfully validates that the validated cache file is created on first load, read on second load, and invalidated when any TOML file in the registry changes.
