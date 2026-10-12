---
tags:
  - '#exec'
  - '#registry-header-requirements'
date: '2026-10-12'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:0f3b30b893bb78f89c22577b28c0f05351aa55cd62656b338d137ebf9b08b407'
related:
  - "[[2026-10-12-registry-header-requirements-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `registry-header-requirements` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S01` `M` `dev/registry/pipeline/semantic_map.py`
- `S01` `M` `dev/registry/pipeline/semantic_map_validation.py`
- `S01` `M` `dev/registry/pipeline/export_field_schema.py`
- `S01` `M` `dev/registry/pipeline/export_fragment_provenance.py`
- `S01` `M` `dev/registry/pipeline/export_fragment_provenance_projection.py`
- `S01` `M` `dev/registry/pipeline/render_check.py`
- `S01` `M` `dev/registry/filing_export_generated_verification.py`
- `S01` `A` `dev/registry/pipeline/tests/test_reviewed_header_requirements.py`
- `S01` `verify:` `pytest dev/registry/pipeline/tests/test_reviewed_header_requirements.py (12 passed)` -> `pass`
- `S01` `verify:` `ruff check, ruff format --check, ty on touched pipeline files` -> `pass`
- `S01` `verify:` `dev/registry/tests/test_semantic_map_fragment_loading.py loader-owner test (extra enum import; fixed)` -> `fail`
- `S01` `verify:` `targeted rerun: loader-owner, generated-tree-state, export-tree, 111/216/360 registry, 360 header export, generated trees excl. 303/189/194 (358 passed; 1 failed: all-manifest attestation test hitting the 189 inheritance chain, not attributable to this change)` -> `pass`
- `S02` `M` `dev/registry/mappings/modelo_111/2019/0002-page-01.toml`
- `S02` `M` `src/cadrumo/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/export/0000-export-layout.toml`
- `S02` `M` `src/cadrumo/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/export/0001-record-modelo-111-page-01.toml`
- `S02` `M` `src/cadrumo/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/export/_generation.provenance.json`
- `S02` `M` `src/cadrumo/application/filing/record_field_renderer.py`
- `S02` `M` `src/cadrumo/application/modelo/export.py`
- `S02` `M` `src/cadrumo/application/modelo/profile_export_binding.py`
- `S02` `verify:` `python -m dev.registry.pipeline republish-target 111 2019-y-siguientes aeat-dr-111-2019-v18 2026 1T d6472339...ec15 (temporary record_drift row, retired after)` -> `pass`
- `S02` `verify:` `python -m dev.registry.pipeline check 111 2019-y-siguientes aeat-dr-111-2019-v18 2026 1T (result=matched)` -> `pass`
- `S02` `verify:` `publish-authority --if-stale (identity_digest 63d31969...bdae)` -> `pass`
- `S02` `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_modelo_export_verb.py (24 passed, incl. test_export_modelo_111_refuses_when_profile_name_missing)` -> `pass`
- `S02` `verify:` `ruff, ruff format, ty on touched application files` -> `pass`

## Notes

- `S02` just check-import-boundaries reported `tool_failure` (stale `import_load_targets` metadata and source changing mid-run from concurrent sessions; 15/15 contracts kept, findings only in other sessions' test files)
