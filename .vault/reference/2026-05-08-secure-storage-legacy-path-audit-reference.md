---
tags:
  - '#reference'
  - '#secure-storage-legacy-path-audit'
date: '2026-05-08'
modified: '2026-05-08'
related: []
---



# `secure-storage-legacy-path-audit` reference: `secure-storage-legacy-path-audit reference`

This reference records the focused audit for lingering path-shaped
import/export/storage surfaces after the secure SQL object backend became the
binding persistence layer. The audit covered production code under
`src/aeat/application`, `src/aeat/domain`, and `src/aeat/entrypoints/cli`, plus
adjacent import-contract tests under `tests/import_contract`.

## Findings

| ID | Classification | Surface | Finding | Action |
|---|---|---|---|---|
| SS-PATH-001 | real-regression-candidate | `src/aeat/application/filing/_export.py::export_draft`, `src/aeat/application/filing/_export.py::verify_export` | Filing export writes caller-supplied filesystem output and verify reads caller-supplied filesystem input. This may be an intentional export artifact, but it is the only production filing-data surface found that still directly persists or consumes sensitive payload bytes by path outside `SecureObjectRepository`. | Decide policy explicitly. If export artifacts are allowed, document them as portable user artifacts and ensure no internal storage semantics depend on the path. If not allowed, move exported payloads into secure objects and make CLI download/render a separate artifact action. |
| SS-PATH-002 | real-cleanup | `src/aeat/domain/filing/_repository.py::FilingDraftRepository`, `src/aeat/domain/submission/_repository.py::SubmissionRepository`, `src/aeat/domain/justificante/_repository.py::JustificanteRepository` | Constructors still accept `store_dir` and ignore it. Storage is secure backend backed, but the public API still signals path-based ownership and keeps legacy callers compiling. | Remove ignored `store_dir` parameters and update callers/tests to construct repositories without path arguments. |
| SS-PATH-003 | false-positive | `src/aeat/application/archive/_export.py::create_archive`, `src/aeat/application/archive/_import.py::restore_archive` | Archive export and restore operate through `SecureObjectRepository`. The JSON bundle is a user-requested portable artifact, not a replacement internal storage backend. | Keep archive bundle behavior. Continue treating bundle file writes as explicit import/export artifacts rather than application persistence. |
| SS-PATH-004 | false-positive-with-cleanup | `src/aeat/application/filing/_complementaria.py` | Complementaria helpers still mention amendment directories and path-like IDs, but repository persistence routes through secure backend repositories. The directory shape is mostly validation and legacy locator language. | After repository constructors are cleaned, revisit complementaria naming and helper docstrings to remove path-first language. |
| SS-PATH-005 | acceptable-test-isolation | `src/aeat/entrypoints/cli/test_cli_surface.py`, `src/aeat/entrypoints/cli/test_user_cli_surface.py`, `tests/import_contract/domain/invoices/test_cli.py`, `tests/import_contract/domain/invoices/test_repository.py`, `tests/import_contract/domain/invoices/test_reconciliation.py` | Test `tmp_path`, environment overrides, and local SQLite database setup isolate secure backend state. These are not alternate storage implementations when the repositories still use `SecureObjectRepository`. | Keep isolation fixtures, but avoid passing path parameters into repositories once ignored constructor parameters are removed. |
| SS-PATH-006 | completed-cleanup | `src/aeat/domain/invoices/_service.py`, `tests/import_contract/domain/invoices/_test_repository.py` | The invoice path-shaped bidirectional link API and stale store-dir repository duplicate were removed. | No further invoice action unless new callers reintroduce path-shaped link semantics. |

## Manual Classification Notes

Archive bundle creation is not considered a storage regression because it walks
secure objects and serializes a deliberate operator-facing export artifact.
This differs from repository APIs that accept path parameters for internal
persistence.

Test fixtures that configure `AEAT_DATABASE_URL` or secure object secrets are
acceptable when they exercise the real secure backend. Tests become regressions
when they preserve obsolete repository signatures such as `store_dir` or assert
filesystem envelope paths that no longer exist.

The highest-confidence next slice is `SS-PATH-002`: remove ignored `store_dir`
constructor parameters from secure-backed repositories and update direct
callers. `SS-PATH-001` needs an explicit product/security policy decision before
changing behavior because exported tax files may be legitimate user artifacts.
