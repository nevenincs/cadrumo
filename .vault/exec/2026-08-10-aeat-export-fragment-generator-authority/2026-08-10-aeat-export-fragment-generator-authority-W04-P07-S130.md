---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:7f59696238d7487012b414487e2655fd21dcd08596be5670e8017e220f60228d'
step_id: 'S130'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Declare the three remaining Modelo 390 generated-export bootstrap targets for revisions 2023, 2024, and 2025 through exact modelo, revision, record-design source, source digest, generated layout, CRLF transport, superseded manual layout identity, and one-reference construct pins, and prove wrong-source and supersession-count drift refuse before S21 publication

## Scope

- `dev/registry/pipeline/generated_export_bootstrap_targets.toml`
- `dev/registry/tests/test_generated_tree_cli.py`

## Changes

- Added exact bootstrap declarations for Modelo 390 revisions 2023, 2024, and 2025, preserving the pre-existing 2022 declaration.
- Expanded the concrete target test across all four revisions without casts, `Any`, ignores, or suppressions.
- Preserved the existing wrong-source-digest and exact superseded-reference-count mutation gates.
- `verify:` `uv run --no-sync pytest -q dev/registry/tests/test_generated_tree_cli.py` -> `19 passed`
- `verify:` `uv run --no-sync basedpyright dev/registry/tests/test_generated_tree_cli.py dev/registry/pipeline/candidate_staging.py` -> `0 errors, 0 warnings, 0 notes`
- `verify:` `uv run --no-sync ruff check dev/registry/tests/test_generated_tree_cli.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/registry/tests/test_generated_tree_cli.py` -> `pass`

## Notes

The verification HEAD bracket drifted from `edfe80c7539431910c2a71b0cc8bc11a0e3852dc` to `697344b883edfcb47252fb2baa680a0df8934034` only across unrelated object-name-declustering Vault and quality-test paths. No measured registry path changed. Read-only CLI replays now pass bootstrap selection and expose separate S21 prerequisites: generated-layout legal-reference closure for 2023 and transitive continuity-metadata staging for 2024-2025.
