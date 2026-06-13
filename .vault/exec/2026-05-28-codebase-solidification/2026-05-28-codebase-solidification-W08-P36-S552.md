---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S552
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P36.S552`

Added real-behavior AST-walk test asserting no duplicate definitions of `canonical_decimal_string` survive across `src/aeat/`.

- Created: `src/aeat/test_w08_p36_dedup.py`

## Description

Three tests cover the dedup invariant without mocks or tautologies:

- `test_canonical_decimal_string_has_exactly_one_definition_site`: walks the entire `src/aeat/` tree via `ast.parse`, counts `FunctionDef` nodes named `canonical_decimal_string`, asserts exactly 1, and asserts that single site lives in `domain/_identifiers.py`.

- `test_financial_decimal_module_is_deleted`: asserts `_decimal.py` no longer exists on disk, preventing silent re-introduction.

- `test_financial_package_canonical_decimal_delegates_to_domain`: imports both `aeat.adapters.inbound.financial.canonical_decimal` and `aeat.domain._identifiers.canonical_decimal_string` in a clean module state and asserts `is` identity, proving the re-export alias genuinely points at the domain function.

## Tests

7 tests pass: 3 new dedup-gate tests + 4 pre-existing `test_decimal.py` tests that now exercise the domain implementation via the alias.
