---
tags:
  - '#audit'
  - '#registry-loader-boundary'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---



# `registry-loader-boundary` audit: `loader fragment compiler extraction boundary audit`

## Scope

Assessed `src/aeat/domain/calculations/registry/_loader.py` for the
`P04.S19` fragment-compiler extraction boundary. The file is dirty in the
shared worktree with formatting-only changes, so this slice records extraction
shape only and does not edit loader code.

## Findings

- **Pass:** `_loader.py` is 788 working-tree lines, below the 1,000-line
  monolith threshold, but it owns several distinct responsibilities.
- **Clear extraction candidate:** The fragment compiler is a contiguous helper
  cluster from `_load_modelo_manifest` through `_reject_duplicate_appended_table_ids`.
  This cluster compiles directory-mode revision fragments into the same raw
  `revisions` map accepted by single-file mode.
- **Keep in loader:** `load_modelo_file`, `load_modelo_directory`,
  `load_modelo_path`, `load_modelo_source`, `load_registry_tree`, and
  `discover_modelo_sources` should remain the public loader spine. Moving those
  names would create avoidable public API churn.
- **Keep in loader:** Shared catalogue loading and registry-tree cache
  fingerprinting should stay with the root loader until a separate cache
  boundary audit exists. Those helpers own legal catalogue merge semantics and
  authorization-fragment cache invalidation, not TOML fragment compilation.
- **Extraction module shape:** The safe next module is a private helper such as
  `_loader_fragments.py` exporting only the fragment compiler functions needed
  by `_loader.py`. It should not expose modelo-specific APIs or new layout
  semantics.
- **Regression surface:** The eventual extraction should be guarded by
  directory-mode loader tests, duplicate-fragment tests, M100/M200 directory-mode
  load checks, and the existing registry reviewability tests. No schema
  semantics should change.
- **Worktree constraint:** Current `_loader.py` diff is formatting-only around
  long `RegistryLoadError` lines and duplicate-id comprehensions. It is peer WIP
  and should not be overwritten or normalised by the extraction slice.

## Recommendations

Close `P04.S19` as an assessment-only step. The implementation slice, when
opened, should:

1. Move only `_load_modelo_manifest`, `_load_modelo_revisions`,
   `_merge_revision_file`, `_merge_revision_directory`,
   `_merge_revision_fragment`, `_merge_revision_fragment_field`,
   `_merge_singleton_table_fragment`, `_merge_export_layout_fragments`,
   `_merge_export_layout_by_id`, `_merge_table_array_fragments`,
   `_merge_table_fragment_by_id`, and `_reject_duplicate_appended_table_ids`.
2. Keep `_as_toml_table`, `_toml_table_id`, and `_reject_local_catalogues`
   either in `_loader.py` or move them only if both loader and fragment compiler
   imports stay acyclic and private.
3. Preserve all public imports from `aeat.domain.calculations.registry`.
4. Run path-scoped loader tests before commit; do not broaden to full registry
   CI while unrelated registry modules remain dirty.

## Codification candidates

None. The extraction rule is already covered by the existing generic
no-modelo-specific-loader architecture constraint.
