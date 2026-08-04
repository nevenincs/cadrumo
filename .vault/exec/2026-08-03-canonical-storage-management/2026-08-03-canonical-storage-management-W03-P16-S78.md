---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:5fd293a92fa76001dbd5469b77525ab9c3a0c33add1449d1a73b18a643e21b5e'
step_id: 'S78'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---
# Burn down the incidental literal corpus one test package at a time across the roughly 108 files carrying path-valued overrides and the roughly 350 hand-rolled override sites, each package gated by the provenance gate scoped to it plus its own suite

## Scope

- `src/cadrumo/tests/`

## Description

- Partial progress only. This record covers a single named ten-file batch
  scoped to the per-bucket database path/filename literal
  (`storage_root / "buckets" / bucket_id / "db" / "cadrumo.db"` and its
  `BUCKET_DATABASE_FILE` taxonomy member), not the Step's full ~108-file /
  ~350-site corpus. `S78` stays unchecked; a ten-file batch against a
  stated ~108 would misrepresent the Step as closed.
- Migrated three files (four occurrences) onto `bucket_paths(...)
  .database_file`: `entrypoints/cli/_config/tests/test_certificate.py`
  (3x, each feeding `_blocking_certificate_secret_event_commit(db_path)` --
  scaffolding to locate the file, not the subject),
  `domain/tests/test_runtime_repository_enrollment.py` (2x, splitting the
  two literals on one expression -- kept `tmp_path / "cadrumo-storage"` as
  the default-settings-root claim, migrated only the
  `buckets/.../db/cadrumo.db` tail), `entrypoints/cli/tests/
  test_workflow_surface.py` (1x, feeding a raw-bytes plaintext-leak check).
  All green under their real markers.
- Declared, not migrated: `core/tests/test_storage_route_classification.py`
  (7 occurrences). `classify_storage_route`'s `database_path` assertions
  check an end-to-end round trip (Settings URL derivation plus
  classification) against the real on-disk shape, independent of what
  `bucket_paths()` computes internally -- migrating collapses the
  assertion to the accessor compared against itself. Two of the seven are
  `not (...).exists()` refusal guards for the former-product `aeat.db`
  case: an absence assertion is trivially satisfied by a wrong path, so a
  literal is the only form that still fails loudly if the accessor pointed
  elsewhere. Added a module docstring recording both reasons, matching the
  declaration already present in `test_layout.py` and
  `test_login_throttle.py`.
- Confirmed two of the ten pre-identified files carry no genuine
  occurrence of this Step's stated literal shape: `tests/
  test_storage_provenance_gate.py`'s only hit is a synthetic
  detector-input string inside the provenance gate's own AST-scanner test,
  not a real path assertion (and its `PENDING_ENROLLMENT` table is already
  the closed empty tuple); `core/tests/test_storage_taxonomy.py`'s `"db"`
  literal is `BUCKET_DATABASE` (the directory), a sibling taxonomy member
  outside this Step's `BUCKET_DATABASE_FILE` scope, and is already the
  taxonomy accessor's own correct self-test oracle. Neither file was
  edited.
- Confirmed the remaining named files needed no action: `core/tests/
  test_storage_taxonomy_name_unification.py` already carries an explicit
  R14 declaration for the same discrimination (found during `S77`);
  `bucket/tests/test_layout.py` and `bucket/tests/test_keystore_paths.py`
  already carry theirs (also `S77`); `tests/test_secure_sql.py` was
  confirmed still dirty with unrelated peer WIP and was not touched.
- Ran the full suite for every edited or read module
  (`test_certificate.py` and `test_workflow_surface.py` under
  `-m integration`, the rest under the default unit marker): all green.

## Outcome

Four occurrences across three files migrated onto the canonical
accessor; seven occurrences in one file declared as deliberate pins with
an inline rationale; two of the ten pre-identified files found to carry
no genuine occurrence of the Step's stated literal shape. `S78` remains
open: this batch closes ten named files against the Step's ~108-file
corpus, not the Step itself.

## Notes

No incidents, no data loss, no `rm`/`Remove-Item` of any form. The
provenance-gate and taxonomy false positives in the originally-handed-off
file list were resolved by reading, not by editing -- two files were
correctly left untouched rather than churned against a stale count.
