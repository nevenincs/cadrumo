---
tags:
  - '#exec'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S03'
related:
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-plan]]'
---

# `no-synthetic-sede-live-surfaces` `P01.S03`

Updated registry policy tests for the AEAT-hosted no-synthetic invariant.

- Modified: `src/aeat/domain/calculations/registry/test_remote_state_guard.py`
- Modified: `src/aeat/domain/calculations/registry/test_authenticated_simulator_surface.py`

## Description

The tests now verify that AEAT-owned `agenciatributaria.gob.es` and `aeat.es`
hosts reject synthetic input at both schema and guard-policy construction time.
The remaining synthetic-positive examples are limited to non-AEAT hosts so the
test suite still proves the invariant is host-scoped rather than a blanket ban
on local replay or off-AEAT simulator evidence.

## Tests

`uv run --no-sync pytest -q src\aeat\domain\calculations\registry\test_remote_state_guard.py src\aeat\domain\calculations\registry\test_authenticated_simulator_surface.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py` passed with 133 tests.
