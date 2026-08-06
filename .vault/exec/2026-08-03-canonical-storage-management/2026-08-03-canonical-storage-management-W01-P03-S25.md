---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:8933bb9a1f2c5f04254b0ded464cd0b9678fe0762c2325009396ffa11b5ea1a5'
step_id: 'S25'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Collapse the twin reset-journal directory-name declaration onto the taxonomy member, gated by the existing parity pin rewritten to compare the application constant against the taxonomy rather than against a second constant

## Scope

- `src/cadrumo/application/_config_reset_repository.py`

## Description

- Add `StorageCategory.CONFIG_RESET_JOURNAL` to the core taxonomy: FIXED
  override policy (no dedicated settings field exists to relocate it
  independently of the storage root -- the same shape as `BUCKETS` and
  `ACTIVE_PROFILE_POINTER`), `UNBOUNDED_BY_DESIGN` lifecycle, `STATE`
  grouping, `consumer_module="application/_config_reset_repository.py"`.
- Re-point both prior standalone `CONFIG_RESET_JOURNAL_DIRNAME` constants
  (`application/_config_reset_repository.py` and `adapters/persistence/
  storage/_storage_path_definitions.py`) to read `storage_location(
  StorageCategory.CONFIG_RESET_JOURNAL).subpath`.
- Rewrite the parity-pin test (`test_persisted_format_enrollment.py::
  test_application_owned_journal_name_agrees_with_the_registry`) to compare
  the application constant against the taxonomy directly, not against the
  second (adapter-layer) constant it previously checked.
- Confirmed byte-identical resolution ("reset-operations") for both
  constants and the taxonomy read.
- Found and fixed fallout from the existing suite (not by inspection): the
  directory-agreement gate's one pre-existing named exemption for
  `config_reset_journal` became stale the moment its run matched a declared
  subpath, and its own anti-rot test caught it. Emptied the exemption dict
  (kept as a live, documented dict rather than deleted) and updated the
  module docstring.

## Outcome

`CONFIG_RESET_JOURNAL_DIRNAME` now has exactly one declaration
(`StorageCategory.CONFIG_RESET_JOURNAL`'s subpath), read from two sites
rather than declared twice. This is the taxonomy member `S108` needs to
exist before it can collapse the application-layer duplicate onto it.
Full storage/core/application suite re-run clean: 1848 passed (one
pre-existing, environment-dependent failure in `test_config_reset.py`
confirmed unrelated by running it against a `git archive` extraction of the
pristine pre-change HEAD, where it fails identically).

## Notes

None. No skipped work, no scaffolds left in code. Landed together with S64
in commit 8c94b7937b.
