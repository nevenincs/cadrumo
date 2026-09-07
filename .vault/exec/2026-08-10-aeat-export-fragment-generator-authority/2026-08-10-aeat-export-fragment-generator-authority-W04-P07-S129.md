---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:3956df7fed76b0284f04301408c6c29d8d81fe9856583a0b090fb2a0615039fc'
step_id: 'S129'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Define one shared candidate-staging boundary that excludes both generated export and superseded manual export_layouts authority, stages the required supplementary Orden closure, applies only an explicit count-pinned bootstrap retargeting of superseded construct members, and expands the authored M390 2022 construct to the generated layout's exact legal-reference closure; use the boundary in the operator CLI and enrolled drift gate, and prove the real bootstrap candidate validates without consulting either tree

## Scope

- `dev/registry/pipeline/`
- `dev/registry/tests/`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/constructs/`

## Changes

- `A` `dev/registry/pipeline/candidate_staging.py`
- `M` `dev/registry/pipeline/_export_tree.py`
- `M` `dev/registry/pipeline/cli.py`
- `M` `dev/registry/pipeline/generated_export_bootstrap_targets.toml`
- `M` `dev/registry/pipeline/render_check.py`
- `M` `dev/registry/tests/test_generated_export_trees.py`
- `M` `dev/registry/tests/test_generated_tree_cli.py`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/constructs/0001-constructs.toml`
- `M` `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`
- `A` `.vault/audit/2026-09-07-aeat-export-fragment-generator-authority-s129-candidate-staging-audit.md`
- `M` `.vault/index/aeat-export-fragment-generator-authority.index.md`
- `verify:` `uv run --no-sync pytest -q dev/registry/tests/test_generated_tree_cli.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/registry/tests/test_generated_export_trees.py::test_m390_bootstrap_isolation_excludes_both_export_authorities_and_keeps_required_support` -> `pass`
- `verify:` `uv run --no-sync python -u -c "from dev.registry.pipeline.cli import app; app()" check 390 2022 aeat-dr-390-2022 2022 0A` -> `pass`
- `verify:` `uv run --no-sync basedpyright dev/registry/pipeline/candidate_staging.py dev/registry/pipeline/cli.py dev/registry/pipeline/render_check.py dev/registry/tests/test_generated_tree_cli.py dev/registry/tests/test_generated_export_trees.py` -> `pass (0 errors, 0 warnings, 0 notes)`
- `verify:` `uv run --no-sync ruff check <owned-python-files>` -> `pass`
- `verify:` `uv run --no-sync ruff format --check <owned-python-files>` -> `pass`
