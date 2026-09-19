---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:6a69fe213807549b0deec0aae2dd8a367d2fc5b7a82a00684cc36104b8b1335f'
step_id: 'S18'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Test recipe discovery, command forwarding, safe defaults, and the absence of implicit live mutation

## Scope

- `dev/quality/tests/test_object_name_declustering_recipe.py`

## Changes

- `M` `justfile`
- `A` `dev/quality/tests/test_object_name_declustering_recipe.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_declustering_recipe.py` -> `pass`
- `verify:` `just --unstable --dump --dump-format json` -> `pass`
- `verify:` `just --list` -> `pass`
- `verify:` `just --show fix-object-names` -> `pass`
- `verify:` `just --dry-run fix-object-names` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/quality/tests/test_object_name_declustering_recipe.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/tests/test_object_name_declustering_recipe.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/tests/test_object_name_declustering_recipe.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright dev/quality/tests/test_object_name_declustering_recipe.py` -> `pass`
- `verify:` `uv run --no-sync python -m compileall -q dev/quality/tests/test_object_name_declustering_recipe.py` -> `pass`
- `verify:` `git diff --check -- dev/quality/tests/test_object_name_declustering_recipe.py justfile` -> `pass`
- `verify:` `independent current-byte S18 operator-safety review` -> `pass`

## Notes

Shared-tree commit `05a2351b63` landed the initial S18 test module, and `2564cb18ad` landed the remaining detector teeth plus the test-exposed `-NoProfile` recipe correction. The Step Record scaffold landed in mixed commit `2019512aff`. This record claims only the two implementation paths above.
