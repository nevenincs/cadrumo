---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:044c348380ce31147fb2ca565cd7f34d563cf38d2ec8f5a8bb5bb568080de162'
step_id: 'S16'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Run checkpoint A once on representative source/enrollment and encoded-candidate fixtures; freeze lane contracts and preserve a runnable paired JSON baseline before retiring old APIs

## Scope

- `dev/registry/tests`

## Changes

- `A` `dev/registry/benchmark_authority.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_authority_component_contract.py`
- `verify:` `checkpoint A: pytest focused selection` -> `pass` (41 passed)
- `verify:` `checkpoint A: ruff check focused selection` -> `pass`
- `verify:` `checkpoint A: ty check focused selection` -> `pass`
