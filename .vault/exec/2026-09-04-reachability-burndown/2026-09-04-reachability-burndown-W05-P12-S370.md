---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:a92f4474bff4a81dcfd0343a6029549f9193b0a13b6156f55542672c115f24ee'
step_id: 'S370'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unconsumed filing-draft repository Protocol and adapter documentation that falsely described it as a live port.

## Scope

- `domain filing protocols`
- `filing persistence adapter documentation`
- `concrete repository tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/domain/filing/protocols.py`
- `M` `src/cadrumo/adapters/persistence/profile/__init__.py`
- `M` `src/cadrumo/adapters/persistence/profile/_filing_runtime.py`
- `M` `src/cadrumo/adapters/persistence/profile/filing_drafts.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/filing/protocols.py src/cadrumo/adapters/persistence/profile/__init__.py src/cadrumo/adapters/persistence/profile/_filing_runtime.py src/cadrumo/adapters/persistence/profile/filing_drafts.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/application/filing/tests/test_repository.py -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`

## Notes

The broader `src/cadrumo/domain/filing/tests/test_secure_storage_roundtrip.py` module remains red in `test_calculation_revision_observations_survive_encrypted_storage` because its calculation-revision fixture has no persisted parent WorkUnit; this step did not alter that repository or fixture.
