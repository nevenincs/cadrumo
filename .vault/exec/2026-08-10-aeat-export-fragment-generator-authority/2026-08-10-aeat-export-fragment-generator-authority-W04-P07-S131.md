---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:38c2ffe03fffd55cdde7379d1d78d09a40e1d0d3803c7576f8a95299391a983c'
step_id: 'S131'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Make generated-export continuity witnesses close transitively over every source-declared predecessor instead of copying only the target revision immediate predecessors, centralize that staging boundary for the operator CLI and enrolled gate, and expand the Modelo 390 2023 through 2025 constructs to the exact legal-reference unions required by their generated layouts before S21 publication

## Scope

- `dev/registry/pipeline/candidate_staging.py`
- `dev/registry/pipeline/cli.py`
- `dev/registry/tests/test_generated_export_trees.py`
- `dev/registry/tests/test_generated_tree_cli.py`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/constructs/0001-constructs.toml`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/constructs/0001-constructs.toml`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/constructs/0001-constructs.toml`

## Changes

- Centralized continuity metadata staging and closed it transitively over declared predecessor edges.
- Added a concrete Modelo 390 2025 witness test proving the staged chain is exactly 2022, 2023, and 2024.
- Preserved the existing Modelo 303 missing and mismatched predecessor refusal tests through the shared helper.
- Expanded each 2023-2025 construct by its exact missing generated-layout legal references while retaining its pre-existing calculation authorities.
- `verify:` focused continuity tests -> `2 passed`
- `verify:` real CLI checks for Modelo 390 2023, 2024, and 2025 -> each `result=publishable_absence`
- `verify:` `basedpyright` over all four edited Python files -> `0 errors, 0 warnings, 0 notes`
- `verify:` Ruff check -> `pass`
- `verify:` Ruff format -> `pass`

## Notes

Vaultspec RAG failed at the service boundary for both code and Vault queries. Discovery therefore used the exact S21, continuity, construct, and candidate-staging identifiers only. All verification HEAD brackets were stable at `0038adeb5bf421f0d6eebdb2a4e29d532179f9e1`.
