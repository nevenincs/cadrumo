---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:347f331381eaf137e337317f697784c32c6781b1e2aea5f6520f1087544189a4'
step_id: 'S110'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Require draft filing coordinates in runtime, export and verification; use selected source/layout dependencies and preserve stale-draft refusal

## Scope

- `src/cadrumo/application/filing`

## Changes

- `M` `src/cadrumo/application/filing/runtime.py`
- `M` `src/cadrumo/application/filing/export.py`
- `M` `src/cadrumo/application/filing/export_verification.py`
- `M` `src/cadrumo/application/filing/tests/test_filing.py`
- `M` `src/cadrumo/application/filing/tests/test_runtime_profile_export_bindings.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/filing/tests/test_filing.py src/cadrumo/application/filing/tests/test_runtime_profile_export_bindings.py -q` -> `pass`
