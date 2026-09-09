---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:5f29cb83f17c9e47c8c42b556f5ba457739dabb557c98b676f769ec96884f75b'
step_id: 'S345'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Replace the test-inventory ownership policy engine and embedded Python fixtures with direct public helper behavior tests.

## Scope

- `test inventory suite`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `dev/tests/test_test_inventory.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q dev/tests/test_test_inventory.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/tests/test_test_inventory.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
