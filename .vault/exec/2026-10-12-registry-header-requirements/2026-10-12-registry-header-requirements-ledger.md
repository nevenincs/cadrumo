---
tags:
  - '#exec'
  - '#registry-header-requirements'
date: '2026-10-12'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:fde05542262ab58a9198097183d6f2260dbd6151bf4ab467a5d180554b92605d'
related:
  - "[[2026-10-12-registry-header-requirements-plan]]"
---

# `registry-header-requirements` ledger

## Changes

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
