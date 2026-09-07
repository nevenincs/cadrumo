---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:898754fbb3a6064def8701eb8f1d0cdf6f4ddee839cadc5cc609bb74c2cc7aba'
step_id: 'S21'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Publish the four exact-source Modelo 390 revision trees and provenance manifests through the canonical validated CLI, replace each construct manual layout member with its generated identity, delete every superseded export_layouts tree with no fallback, enroll all four published revisions in the generated-tree drift gate, and prune the consumed bootstrap declarations so no authorization outlives its cause

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/`
- `dev/registry/pipeline/generated_export_bootstrap_targets.toml`
- `dev/registry/tests/test_generated_export_trees.py`
- `dev/registry/tests/test_generated_tree_cli.py`

## Changes

- Published four provenance-attested generated export packages through the canonical CLI.
- Deleted 66 superseded manual export-layout fragments and retargeted all four constructs to generated layout identities.
- Enrolled the 2023, 2024, and 2025 revisions beside the already enrolled 2022 revision.
- Pruned all four consumed Modelo 390 bootstrap declarations and their now-dormant direct declaration test.
- Verified the full registry selects exactly one generated layout for each year 2022-2025.
- `verify:` `pytest -q dev/registry/tests/test_generated_export_trees.py -k m390` -> `9 passed`
- `verify:` canonical CLI `check` for all four Modelo 390 revisions -> each `result=matched`
- `verify:` strict Basedpyright over the edited tests -> `0 errors, 0 warnings, 0 notes`
- `verify:` Ruff check -> `pass`
- `verify:` Ruff format -> `pass`

## Notes

The final registry-load bracket drifted from `d035e7ab956335a7a9ea3c520a33bdcd668c2c57` to `d427ab6c981be9a0b825e4a4d01e3b81a90434df` only across unrelated object-name-declustering Vault documents. No measured registry or Modelo 390 path changed.
