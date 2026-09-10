---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:a183e5a9231d120d76abcfd76005c7b80f5cf2af24cff695bf288407fc52ade2'
step_id: 'S14'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [L | opus-medium] Make export references a derived field: the loader computes them from the edition layout's own back-pointer and refuses an authored value. Delete the pipeline module that currently writes them onto casilla declarations. Proof: an authored value is refused; computed values match today's declarations byte for byte.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/export_field_casilla.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_casilla_export_refs_derivation.py`
- `M` `src/cadrumo/domain/calculations/registry/_loader_internals.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_exports.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_record_sections.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_revision_context.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_revision_sections.py`
- `M` `src/cadrumo/domain/calculations/registry/export.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_export_projection_refs.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part2.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_revision_edition_round_trip.py`
- `D` `dev/registry/pipeline/_casilla_export_refs.py`
- `M` `dev/registry/pipeline/_tree_publication.py`
- `M` `dev/registry/pipeline/candidate_staging.py`
- `M` `dev/registry/pipeline/cli.py`
- `M` `dev/registry/tests/test_delta_target_publication.py`
- `M` `dev/registry/tests/test_export_tree.py`
- `M` `dev/registry/tests/test_generated_tree_cli.py`
- `M` `src/cadrumo/_data/registry/aeat/modelos/**/*.toml` (1515 files, 11301 `export_refs` keys removed)
- `verify:` dump of all 128 compiled revisions, HEAD code on the frozen snapshot vs new code on the stripped snapshot, under the record-order-then-offset rule -> `pass` (byte-identical, 11301 casillas carrying refs)
- `verify:` `uv run --no-sync pytest test_casilla_export_refs_derivation.py` -> `pass` (8); nine production mutations each fail it
- `verify:` `uv run --no-sync pytest test_delta_target_publication.py` -> `pass` (5)
- `verify:` `uv run --no-sync pytest test_revision_edition_round_trip.py` -> `pass`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `verify:` `uv run --no-sync ruff check`, `ruff format --check`, `ty check` on the changed Python files -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests` -> `fail` (12; 10 identical on an unmodified HEAD worktree, 1 load-sensitive threading wait that passes alone, 1 fixed and re-run green)
- `verify:` `uv run --no-sync pytest dev/registry/tests` -> `fail` (45, every one failing with the same reason on an unmodified HEAD worktree)

## Notes

- The declarado record of modelo 347 is the only `binding_rows` record without `binding_record`, so its 18 row-mapped binding fields are the only edges derived through the record row mapping. Whether those back-references should exist is open for the export lane; it does not block this Step.
- The check that casilla files differ only on their `export_refs` line had no standalone site; it lived inside the deleted writer module.
- The code review is outstanding: the reviewer persona could not be launched from this session.

- The export lane (REGISTRY-TYPE) reviewed the resolver and approved it. Their gates ran against the tree: 95 passed, exit 0, covering generated-tree reproduction, the modelo 200 own-sheet bindings, design sign positions, the hand-authored type column, design agreement, and the derivation tests. The orchestrating session re-ran the derivation, delta-publication and materialisation tests (23 passed) and `registry verify` (exit 0). Landed in c1df8e45a5.
