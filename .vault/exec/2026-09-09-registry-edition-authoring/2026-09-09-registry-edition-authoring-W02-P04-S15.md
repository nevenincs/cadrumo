---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:bbe92952de0aa6db747444a47ded1226b2dda7d7947e4f92c8c17d985a7de183'
step_id: 'S15'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [M | sonnet-high] Remove the edition key from formula and binding identifiers by programmatic rewrite, with every reference updated in the same pass. Bounded rename, but references must not break. Proof: no identifier in these two families contains an edition key, and registry validation is clean.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`

## Changes

- `A` `dev/registry/rename_formula_binding_identifiers.py`
- `M` 2765 files across 7 modelos (`100`, `131`, `200`, `202`, `210`, `353`, `714`): 6390 formula/binding declarations renamed (1224+270+12+27+10+3+4844), plus every casilla, formula, binding, construct, relation, and `export_layouts` reference to a renamed id, plus `dev/registry/mappings/modelo_390` reverted (see Notes) leaving no mapping-file changes
- `M` `src/cadrumo/domain/calculations/registry/tests/test_revision_edition_round_trip.py` (stale hardcoded modelo-131 binding-id literals in the export round-trip scenario, updated to the renamed ids)
- `verify:` `dev/registry/rename_formula_binding_identifiers.py` (measure mode, post-apply) -> `pass` (0 formula ids and 0 binding ids embed an edition key across the 55 in-scope modelos; 707 modelo-390 binding ids still embed one, correctly reported as deferred)
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass` (exit 0)
- `verify:` `uv run --no-sync pytest test_revision_inherited_reference_resolution.py test_revision_edition_round_trip.py test_casilla_export_refs_derivation.py` -> `pass`
- `verify:` `uv run --no-sync ruff check`, `ruff format --check`, `ty check` on `dev/registry/rename_formula_binding_identifiers.py` -> `pass`

## Notes

- Modelo 390 is excluded from this rewrite by design, not oversight: its generated `revisions/*/export/` trees (2022-2025) copy the pre-rename binding ids into field and provenance records, and `registry verify` refuses a renamed source map sitting beside a not-yet-regenerated tree (confirmed empirically: exactly 707 "unknown binding" failures, one per renamed reference, all in modelo 390). The tool measures and reports modelo 390's 707 embedding bindings but never writes them; its rename and the export lane's republish of those four trees must land in the same change. That list is handed to the export lane rather than regenerated here.
- Another session committed an equivalent rename (`562fcb9848 refactor(registry): normalize binding and formula identifiers`) to this shared worktree's branch while this Step was in progress; the two converged on byte-identical output for the 7 applied modelos and the rewrite script. That commit's copy of `test_revision_edition_round_trip.py` still carried the stale hardcoded modelo-131 binding-id literals fixed here; that fix remains uncommitted, as this persona never stages or commits.
