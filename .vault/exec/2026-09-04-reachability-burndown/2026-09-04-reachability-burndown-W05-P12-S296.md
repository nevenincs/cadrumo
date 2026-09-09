---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:5ea777edc36dfaaccda736aadae666657b689ccf0add7b2a307d99971fdcecae'
step_id: 'S296'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the source-wide text-writer newline AST gate, its hard-coded corpus floors, production-path exemptions, self-mutating allowlist tests, and stale lint override; retain newline correctness at owning writers and formatters.

## Scope

- `development newline census test`
- `lint configuration`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `dev/tests/test_text_writer_newline_pinning.py`
- `M` `pyproject.toml`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "text_writer_newline_pinning|MIN_SCANNED_MODULES|_MINIMUM_SCANNED_BY_TREE|text-writer newline gate" src dev justfile pyproject.toml` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`

## Notes

The concurrent exact snapshot reports 243 unused symbols, 31 unreachable modules, and zero orphan tests. The one-symbol increase from the preceding snapshot is outside this development-test-only deletion, which changes no shipped reachability edge.
