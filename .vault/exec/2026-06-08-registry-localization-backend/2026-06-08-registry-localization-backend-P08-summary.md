---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P08` phase summary

Phase P08 rolled out localized help text configurations for Modelo 100, Modelo 200, and Modelo 303.

## Key Accomplishments

- Authored `en.toml`, `ca.toml`, `hu.toml` files mapping labels and help texts.
- Extended registry locales parity tests to assert correct load and translation retrieval.
- Aligned global codebase-to-locale key mappings after adding new CLI keys.

## Verification Results

- Verified via `pytest src/aeat/domain/calculations/registry/tests/test_registry_locales_parity.py` and global `test_parity.py`.
