---
name: tests-live-under-domain-tests-folders
trigger: always_on
---

# Tests live under domain tests folders

Every Python test file must live under a parent `tests/` directory at the
narrowest owning package or architectural boundary. Naked `test_*.py` files
beside implementation modules are forbidden.

This keeps Rust-style local ownership while removing implementation namespace
pollution. Without the rule, naked colocated tests reappear and undo the
mechanical topology invariant the test layout depends on.

## How

- **Good:** `src/cadrumo/application/modelo/tests/test_work_addressing.py` tests
  the `cadrumo.application.modelo` surface from its local test folder.
- **Bad:** `src/cadrumo/application/modelo/test_work_addressing.py` sits beside
  implementation modules and pollutes the code namespace.

Source: ADR `2026-06-05-test-topology-refactor-adr`.
