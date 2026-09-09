---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:5e5ec66c0b406ab8c45215c3da085f36366ab5dcd2eff51bb30472e8ff6a539b'
step_id: 'S295'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the hand-maintained identifier-namespace adjudication gate and the two unreachable profile snapshot DTOs it classified; retain the canonical UserProfileSnapshot domain owner and real profile service behavior.

## Scope

- `identifier namespace enrollment census`
- `user-profile command DTOs`
- `focused profile tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/application/user_profile/commands.py`
- `D` `dev/identity/tests/test_identifier_namespace_enrollment_gate.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n <deleted DTO and adjudication-list names> src dev` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/user_profile/commands.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/user_profile/tests/test_services.py` -> `fail`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`

## Notes

The focused service suite passed 20 tests; one peer-owned failure observed the bundled registry changing during cache fingerprinting. Exact reachability moved from 244 to 242 unused symbols with 31 unreachable modules and zero orphan tests.
