---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S52'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W07.P12.S52`

## Description

- Validate the selected `application/modelo` isolation pattern against the central `aeat.tests.secure_sql` helper surface before repair.
- Add a real-behavior helper test proving `isolated_cli_runtime_profile` routes workflow state plus default modelo work-unit and calculation-revision repositories into the active bucket database.
- Keep the validation on real repositories and real encrypted SQLite; no fakes, stubs, mocks, monkeypatch repair, skip, or xfail.

## Outcome

Closed.

The candidate replacement pattern is valid for the S51 repair target. `isolated_cli_runtime_profile` creates the active bucket route, workflow state can save through `workflow_state_repository()`, and default `WorkUnitCatalogueRepository()` plus `CalculationRevisionCatalogueRepository()` resolve to the same active bucket id and persist into that bucket database.

An initial validation attempt tried to call `register_minimal_profile(...)` inside `isolated_cli_runtime_profile`; that failed with `ProfileNotFoundError`, which is correct because CLI runtime isolation provisions runtime storage and directories, not profile bootstrap. The final test intentionally validates repository routing without claiming the helper creates profile aggregates.

Verification:

- `uv run --no-sync pytest -q src/aeat/tests/test_secure_sql.py` -> 5 passed.
- `uv run --no-sync ruff check src/aeat/tests/test_secure_sql.py` -> all checks passed.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` -> 2 passed.

## Notes

No HIGH or CRITICAL issue was identified in this validation step.
