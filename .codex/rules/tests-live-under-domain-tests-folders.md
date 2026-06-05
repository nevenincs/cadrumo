---
name: tests-live-under-domain-tests-folders
trigger: always_on
---

# Tests live under domain tests folders

## Rule

Every Python test file must live under a parent `tests/` directory at the narrowest owning package or architectural boundary; naked `test_*.py` files beside implementation modules are forbidden.

## Why

The `2026-06-05-test-topology-refactor-adr` decision keeps Rust-style local ownership while removing implementation namespace pollution. Without this rule, future agents can reintroduce naked colocated tests and undo the mechanical topology invariant the refactor depends on.

## How

- Good: `src/aeat/application/modelo/tests/test_work_addressing.py` tests the `aeat.application.modelo` surface from its local test folder.
- Bad: `src/aeat/application/modelo/test_work_addressing.py` sits beside implementation modules and pollutes the code namespace.