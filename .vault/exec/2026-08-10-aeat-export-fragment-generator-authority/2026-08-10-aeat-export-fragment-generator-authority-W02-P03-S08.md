---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:ba528cdd97cfaffcad61460e82af0f0d445f5dab0b52244ec4c2024b00198371'
step_id: 'S08'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Render the complete target export tree with stable partitioning and canonical TOML serialization

## Scope

- `dev/registry/_export_tree.py`
- `dev/registry/tests/test_export_tree.py`
- `dev/registry/tests/test_generated_tree_check.py`
- `src/cadrumo/domain/calculations/registry/__init__.py`

## Description

- Preflight the complete canonical `rtoml` byte plan before creating or writing the target tree.
- Greedily partition oversized records by source field order under the repository's strict reviewability baselines.
- Use independent zero-padded record and part identifiers so repartitioning one record does not rename its first fragment or any later record.
- Require reviewed literal bytes to agree exactly with the unambiguous official parser constant content.
- Consume encoding and loader APIs only through the public registry facade, without a compatibility shim.

## Outcome

Commit `9b0672c597` implements deterministic same-record field chunking from actual canonical serialization and preserves one complete loader-materialised layout. A real-shaped 245-field record emits stable `part-001` onward fragments below 1,400 lines and 520 characters per line, preserves exact source order, emits every field once, and produces byte-identical output across disjoint generation roots. Missing, ambiguous, wrong-same-width, or wrong-extent official literal content refuses before target creation.

Focused exporter and generated-tree-check verification passed with 36 tests. The complete development registry unit lane passed with 142 tests and 24 configured integration deselections. Loader fragments, public facade boundaries, and TOML reviewability passed with 38 tests. Scoped Ruff check and format passed; scoped BasedPyright reported zero errors, warnings, or notes. The complete import-hygiene run completed with 35 passes and six unrelated shared-tree failures; none referenced the S08 files.

The formal review initially recorded one medium filename-stability finding. Always-numbered `part-001` naming and a direct split-threshold stability assertion closed it; independent re-review reported zero remaining high or medium findings.

## Notes

This Step does not integrate render-profile authority or profile provenance; those remain exclusively in `W02.P03.S32`. No legacy output tree, alias, duplicate fragment, or compatibility surface was introduced.
