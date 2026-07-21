---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S09'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Add UNMODELED_OBLIGATIONS and grow the Modelo enum with recognized-unmodeled obligations (117, 216, 296) carried in NON_REGISTRY_MODELOS.

## Scope

- `src/aeat/core/_modelo.py`

## Description

- Add `UNMODELED_OBLIGATIONS`, a central typed mapping of recognized AEAT
  obligations the registry does not model, each with a description.
- Grow the `Modelo` enum with M117, M216, M296 (grounded against AEAT's published
  catalogue) and fold them into `NON_REGISTRY_MODELOS` so the enum parity gate stays
  green and validate_modelo still raises for them.
- Re-export the constant from the core package and reframe the NON_REGISTRY /
  enum docstrings to cover both retired and recognized-unmodeled members.

## Outcome

The AEAT obligation universe is now `registry ∪ UNMODELED_OBLIGATIONS`, an extensible
edge that ratchets up as obligations are recognized and shrinks as they are modeled.
Core modelo parity and AST string-usage gates stay green; `CANONICAL_MODELO_FLEET`
auto-excludes the new members via its existing `NON_REGISTRY_MODELOS` filter.

## Notes
