---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:7ac2426a196132a15528b1ba8bd447fdbe62486b48e33f635460e7d8d3e19c87'
step_id: 'S242'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unreachable error-module resolve_output_language fallback and export; keep the canonical i18n resolver and preserve logger redaction tests without naming or simulating the dead helper.

## Scope

- `Core error rendering module and registry tests`
- `accepted output-language authority`
- `exact symbol signal`
- `focused error gates`
- `cadence reference`
- `and Step Record.`

## Changes

- `M` `src/cadrumo/core/errors/error_codes.py`
- `M` `src/cadrumo/core/errors/tests/test_registry.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/errors/error_codes.py src/cadrumo/core/errors/tests/test_registry.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s242 src/cadrumo/core/errors/tests/test_registry.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
