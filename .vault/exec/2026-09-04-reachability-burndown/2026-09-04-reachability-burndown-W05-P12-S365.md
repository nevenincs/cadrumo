---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:20a6c0938670b48732b80f4f03b5a96d6c47aed6025d23122b580b6185732367'
step_id: 'S365'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unconsumed rich-progress terminal policy helper and its stale module contract.

## Scope

- `CLI TTY helper`
- `CLI TTY behavior tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_tty.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/_tty.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
