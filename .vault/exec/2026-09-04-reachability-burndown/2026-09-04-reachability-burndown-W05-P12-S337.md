---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:ebe028e8c69cc78756e36d5634d9ba68a41ee390e20e5f2f488c4b3bf37bc4f6'
step_id: 'S337'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove the duplicate source-policy engine from the CI command-spec authority test

## Scope

- `CI command graph test`
- `public API invariants`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `dev/ci/tests/test_command_spec_authority_gate.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_command_spec_authority_gate.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 278 unused symbols.
