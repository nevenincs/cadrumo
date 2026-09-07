---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:637cde0a93ddf479f4735844eb9e82ea27b98afef82dac9522721c531854c351'
step_id: 'S128'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Centralize hash-pinned source-defect declarations in one public pipeline-owned module, wire the operator CLI and generated-tree gate to that catalogue, prove the Modelo 390 render seam, extend temporal-coverage S32 to detect in-file revision enrolment lists, and reconcile S79's landed map and enrolment state without claiming publication.

## Scope

- `dev/registry/pipeline/`
- `dev/registry/tests/`
- `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`
- `.vault/plan/2026-08-14-registry-temporal-coverage-plan.md`

## Changes

- `R` `dev/registry/pipeline/_source_defects.py` -> `dev/registry/pipeline/source_defects.py`
- `M` `dev/registry/pipeline/_export_tree.py`
- `M` `dev/registry/pipeline/_tree_check.py`
- `M` `dev/registry/pipeline/cli.py`
- `M` `dev/registry/pipeline/render_check.py`
- `M` `dev/registry/tests/test_generated_export_trees.py`
- `M` `dev/registry/tests/test_generated_tree_cli.py`
- `M` `dev/registry/tests/test_render_check.py`
- `M` `dev/registry/tests/test_source_defect_declarations.py`
- `M` `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`
- `M` `.vault/plan/2026-08-14-registry-temporal-coverage-plan.md`
- `A` `.vault/audit/2026-09-07-aeat-export-fragment-generator-authority-s128-source-defect-wiring-audit.md`
- `M` `.vault/index/aeat-export-fragment-generator-authority.index.md`
- `verify:` `uv run pytest -q dev/registry/tests/test_source_defect_declarations.py dev/registry/tests/test_generated_tree_cli.py` -> `pass`
- `verify:` `uv run pytest -q dev/registry/tests/test_render_check.py` -> `pass`
- `verify:` `uv run pytest -q --collect-only dev/registry/tests/test_generated_export_trees.py` -> `pass`
- `verify:` `uv run pytest -q dev/registry/tests/test_generated_export_trees.py::test_every_pending_check_mode_entry_names_an_enrolled_tree` -> `pass`
- `verify:` `uv run ruff check <owned-python-files>` -> `pass`
- `verify:` `uv run ruff format --check <owned-python-files>` -> `pass`

## Notes

The exact Modelo 390 CLI check now renders past the adjudicated page-7 literal and reaches the later S21-owned refusal: the generated candidate conflicts with the superseded `export_layouts` tree.
