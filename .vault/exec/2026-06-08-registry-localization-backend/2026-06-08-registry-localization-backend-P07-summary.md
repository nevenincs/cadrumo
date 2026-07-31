---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-07-17'
body_hash: 'sha256:3c62352c76fc252ecec98590445fb60e801205842eb90580f87d06791634404b'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P07` phase summary

Phase P07 implemented compile-time cross-reference validation for manuals within the registry compiling pipeline.

## Key Accomplishments

- Extended `_sources.py` and `_legal.py` with strict Pydantic checks.
- Authored reference validation tests verifying failure and recovery states.
- Verified that all registry manual references point to real structures on disk.

## Verification Results

- Verified via `pytest src/aeat/domain/calculations/registry/tests/test_catalogue_verification.py`.
