---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P03.S06'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P03.S06`

Added three CLI tests covering the dry-run fingerprint, the
`--yes`-required refusal, and the post-reset empty-state load.

- Created: `src/aeat/entrypoints/cli/_config/test_repair_reset_state.py`

## Description

The test module isolates secure-object storage per test via the
standard `AEAT_DATABASE_URL` / `AEAT_SECRET_STORE_BACKEND=unsecured`
fixture pattern used by sibling CLI test modules. It seeds a
readable workflow-state row via `WorkflowStateRepository.save()` so
each test exercises a real envelope.

- `test_reset_state_dry_run_returns_fingerprint_without_deleting_row`:
  invokes `--format json config repair reset-state --dry-run`,
  asserts `dry_run is True`, asserts the fingerprint carries a
  positive `byte_length` and `schema_version == 1`, and asserts the
  underlying secure-object row still exists.
- `test_reset_state_without_yes_or_dry_run_raises_refusal_and_keeps_row`:
  invokes `config repair reset-state` with neither flag, asserts a
  non-zero exit code, and asserts the row is intact.
- `test_reset_state_with_yes_deletes_row_emits_event_and_reload_is_empty`:
  invokes `--yes`, asserts the row is gone, asserts exactly one
  `BucketEventType.WORKFLOW_STATE_RESET` event was appended to the
  bucket-event history, and asserts a fresh `load()` returns the
  empty-state shape (compared via `model_dump(exclude={"updated_at"})`
  since the freshly-constructed reference and the freshly-loaded
  reload bear different `updated_at` defaults).

## Notes

The tests do not rely on test doubles, fakes, mocks, or skips. The
secure-object backend, the bucket-event history repository, the
Typer runner, and the application-layer reset service are all
exercised end-to-end against a real isolated SQLite database.
