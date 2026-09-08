---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:af2bd252bae1d8473218d2544d9fb1725ff5abeca3c6e8828824fec8835fdfe6'
step_id: 'S168'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the production login-gated negative-path registry and its implemented/not-yet-mounted lifecycle machinery, then preserve the archive-export authentication invariant by deriving the mounted leaf from the live CommandSpec graph and exercising the real default-deny bootstrap exemption matcher, including prefix swallowing.

## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`
- `src/cadrumo/entrypoints/cli/tests/test_login_gated_verbs_never_exempt.py`
- `reachability burndown reference`
- `focused bootstrap security gates`
- `live unused-symbol measurement`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_login_gated_verbs_never_exempt.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "LOGIN_GATED_VERB_PATHS|LoginGatedVerb|_NOT_YET_MOUNTED" src/cadrumo -g "*.py"` -> `pass` (zero matches)
- `verify:` `uv run ruff check src/cadrumo/entrypoints/cli/_bootstrap_exempt.py src/cadrumo/entrypoints/cli/tests/test_login_gated_verbs_never_exempt.py` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo/entrypoints/cli/tests/test_login_gated_verbs_never_exempt.py src/cadrumo/entrypoints/cli/tests/test_bootstrap_exempt_entries_resolve.py` -> `fail` (zero tests collected because default selection excludes integration)
- `verify:` `uv run pytest -q -m integration src/cadrumo/entrypoints/cli/tests/test_login_gated_verbs_never_exempt.py src/cadrumo/entrypoints/cli/tests/test_bootstrap_exempt_entries_resolve.py` -> `pass` (62 passed)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (364 exact symbols, down from 365, and 18 orphaned test modules unchanged)

## Notes

The focused test now resolves the already-mounted archive-export leaf from `COMMAND_GRAPH` and tests the live default-deny matcher. The first pytest invocation was not accepted as evidence because the repository's default marker expression collected no integration tests; the explicit integration run is the owning verification.
