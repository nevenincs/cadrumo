---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:fc1f6231118c7f70d6dc272792508ab83204609da9ebd60a806d1eed1a31580c'
step_id: 'S62'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# modelo-100-profile-binding-path-validation

## Scope

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/bindings/`

## Description

- Read the Modelo 100 2025 profile-binding regression suite, which enumerates the full profile population and covers scalar, composite, model-alias, and repeating-collection selectors.
- Ran `uv run --no-sync pytest src/aeat/application/modelo/tests/test_profile_binding_real_path.py -q`.
- Verified all 38 registered Modelo 100 2025 profile bindings against the canonical profile schema and live resolution index; the test retains an absent-fact guard so resolution cannot invent a value.

## Outcome

The current Modelo 100 2025 selector projection is aligned with canonical profile paths and aliases. The focused suite passed 11 tests.

## Notes

The test is a real resolver-and-schema integration test, not a parallel reimplementation of binding logic.
