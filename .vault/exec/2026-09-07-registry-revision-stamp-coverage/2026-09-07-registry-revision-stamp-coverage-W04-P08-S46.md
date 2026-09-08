---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:2be9286353b545ddd5815a16ab053a6106bf4a11618811826509d4d61f0f0fd8'
step_id: 'S46'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Run repository format, type, lint, architecture, and unit quality gates and resolve campaign-owned failures

## Scope

- `pyproject.toml`
- `dev/quality`

## Changes

- `verify:` `uv run basedpyright` -> `pass`
- `verify:` `uv run ruff check <campaign paths>` -> `pass`
- `verify:` `uv run ruff format --check <campaign paths>` -> `pass`

## Notes

`just check-architecture` passed 31 of 32 checks. Its only failure is the
unrelated shared-worktree deletion of `entrypoints/tui/devtools` modules while
28 TUI tests still import them; no campaign-owned import edge was reported.
The final full `basedpyright` run reported zero diagnostics; campaign-scoped
Ruff lint and format checks passed after review remediation.
