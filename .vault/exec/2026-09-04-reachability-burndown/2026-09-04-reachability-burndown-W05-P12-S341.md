---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:9c0cc9d5f13f9a69296e848527d4b95dc85dde98759f11fde901eda8fe1fe13c'
step_id: 'S341'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove the storage-degradation source census while retaining direct canonical exception behavior checks.

## Scope

- `storage degradation error tests and reachability cadence reference`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/tests/test_storage_degradation_errors_are_canonical.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/storage/tests/test_storage_degradation_errors_are_canonical.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/tests/test_storage_degradation_errors_are_canonical.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
