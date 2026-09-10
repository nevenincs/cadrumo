---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:0848e5d38f60142591e145fbf7a3819402311e4de3f625e10d1ac40a678f4e07'
step_id: 'S62'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [M | opus-medium] Implement the amended materialiser contract before the live pilot: (1) the round-trip gate's order assertion compares against the full copy rearranged into the merge order (inherited in predecessor order, superseders in place, new rows appended), with content still element-wise; (2) a row may state source references in addition to the edition's casilla_source_refs, materialising as default followed by additions that inherit with the row, while a full source_refs still replaces (name the additions key canonically); (3) continuidad_origin and continuidad_evidence are never inherited — an inherited row materialises with both unset; (4) the delta-minimality screen judges stated rows only, via a statement-origin marker, not inherited ones. Then re-run the migration script's 303 dry run. Proof: all five 303 successor editions migrate exactly in the dry run, the round-trip gate passes on them, delta-minimality is clean for 303, and the unmigrated corpus is byte-identical.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/_loader_internals.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_surfaces.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_revision_edition_round_trip.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_revision_edition_materialisation.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_revision_edition_reference_defaults.py`
- `M` `dev/registry/analysis/delta_minimality.py`
- `M` `dev/registry/tests/test_delta_minimality.py`
- `M` `dev/registry/edition_delta_migration.py`
- `M` `dev/registry/tests/test_edition_delta_migration.py`
- `verify:` `pytest -n 0` materialisation, reference-defaults, label-inheritance, inherited-reference, export-refs derivation, materialisation entry point, round-trip (pre-merge snapshot) -> `pass` (135 passed)
- `verify:` `pytest -n 0 dev/registry/tests/test_edition_delta_migration.py dev/registry/tests/test_delta_minimality.py` (pre-merge snapshot) -> `fail` (23 passed, 1 pre-existing failure, see Notes)
- `verify:` `ruff check`, `ruff format --check` on the ten files -> `pass`
- `verify:` `ty check` on the ten files (pre-merge snapshot) -> `pass`; at HEAD 836d4f2985 -> `fail` (merge fallout, see Notes)

## Notes

Exception: the proofs ran on the pre-merge snapshot, not HEAD. A shared-branch auto-commit captured most of this work as f7e5d56096. Two later merges from main then broke registry loading at HEAD:

- ae9cf0b0c5: the corpus-catalogue validator rejects `boe-lirpf-art-101-administrator-2015-01-01`, so no registry tree loads through the authority.
- 8543517fe7: removes `loader.load_modelo_directory`, `ValidatedRegistryAuthority.load` and the registry-root parameter of `build_runtime_schema_provider`. 86 files still use them, including every edition-authoring suite and tool.

So every proof ran in a scratch detached worktree at f7e5d56096, carrying this Step's uncommitted dev files. The data snapshot is `git archive f7e5d56096`, which holds S15's identifier rename. `aeat app registry verify` no longer exists (`application/registry` was removed). Its substitute was a full `ValidatedRegistryAuthority.load` of the snapshot under this Step's code: exit 0, 58 modelos, 128 revisions.

Additions key: `additional_source_refs` on a casilla row or its `constraints` table, following the `alternate_bindings` pattern on the canonical `source_refs` stem. The loader refuses it beside `source_refs`, when empty, or where the edition has no `casilla_source_refs`. Statement-origin marker: the typed `CasillaDefinition.inherited_from`, projected once from the loader's label origins. It is excluded from serialisation and refused when authored.

Modelo 303 dry run (`--declare-blocked-roots`, temporary tree, nothing written to live data):

| edition | basis | predecessor | rows | stated | inherited |
| --- | --- | --- | --- | --- | --- |
| 2022 | first (root) | none | 184 | 184 | 0 |
| 2023 | adjacent | 2022 | 198 | 33 | 165 |
| 2024-hasta-08-y-2t | adjacent | 2023 | 199 | 7 | 192 |
| 2024-desde-09-y-3t | adjacent | 2024-hasta-08-y-2t | 207 | 15 | 192 |
| 2025 | adjacent | 2024-desde-09-y-3t | 207 | 6 | 201 |
| 2026-y-siguientes | adjacent | 2025 | 208 | 12 | 196 |

- No edition is blocked. The loaded `inherited_from` markers match the plan's inherited rows exactly.
- Round-trip gate: typed content and merge-order row order are clean on all five successors. Export bytes are unchecked on all five, because no scenario exists.
- Persistent failure: the gate's locale identity fails on 84 casillas per edition, 79 in 2026-y-siguientes, in ca, en and hu only. Spanish is unchanged. The cause is continuity-key catalogue entries that copy the Spanish text, while 2022's occurrence keys carry real translations. The migration's behaviour was left unchanged, per the operator's decision.
- Delta-minimality over the migrated 303: 73 rows judged, 0 findings (49 stated_difference, 24 new_in_edition).
- Unmigrated corpus: all 128 revisions (58 modelos) hash identically under the pre-S62 code (00b45a45cc) and this Step's code on one frozen snapshot. The candidate has 0 inherited rows.
- Teeth: removing each rule from production code fails its tests, and restoring it passes them. Failures per removed rule: lineage-claim stripping 1, additions 6, the inheritance marker 1, gate merge order 2, stated-only judging 1.
- Pre-existing failure: `test_restatement_is_found_through_the_edition_tokens_not_in_spite_of_them` in `dev/registry/tests/test_delta_minimality.py`. After S15's rename (562fcb9848), no modelo 131 binding embeds an edition key, so its premise no longer exists.

Lineages whose inherited labels change (the continuity keys needing translation): 5 in 2023 to 2025 only (`m303-prorrata-actividad-fila-1-cnae` to `-fila-5-cnae`), the rest in all five successors.

m303-deducciones-sector-1-domestic-current-base, m303-deducciones-sector-1-domestic-current-cuota, m303-deducciones-sector-1-domestic-investment-base, m303-deducciones-sector-1-domestic-investment-cuota, m303-deducciones-sector-1-import-current-base, m303-deducciones-sector-1-import-current-cuota, m303-deducciones-sector-1-import-investment-base, m303-deducciones-sector-1-import-investment-cuota, m303-deducciones-sector-1-intra-eu-current-base, m303-deducciones-sector-1-intra-eu-current-cuota, m303-deducciones-sector-1-intra-eu-investment-base, m303-deducciones-sector-1-intra-eu-investment-cuota, m303-deducciones-sector-1-investment-regularisation, m303-deducciones-sector-1-reagp-base, m303-deducciones-sector-1-reagp-cuota, m303-deducciones-sector-1-rectification-base, m303-deducciones-sector-1-rectification-cuota, m303-deducciones-sector-1-total, m303-deducciones-sector-2-domestic-current-base, m303-deducciones-sector-2-domestic-current-cuota, m303-deducciones-sector-2-domestic-investment-base, m303-deducciones-sector-2-domestic-investment-cuota, m303-deducciones-sector-2-import-current-base, m303-deducciones-sector-2-import-current-cuota, m303-deducciones-sector-2-import-investment-base, m303-deducciones-sector-2-import-investment-cuota, m303-deducciones-sector-2-intra-eu-current-base, m303-deducciones-sector-2-intra-eu-current-cuota, m303-deducciones-sector-2-intra-eu-investment-base, m303-deducciones-sector-2-intra-eu-investment-cuota, m303-deducciones-sector-2-investment-regularisation, m303-deducciones-sector-2-reagp-base, m303-deducciones-sector-2-reagp-cuota, m303-deducciones-sector-2-rectification-base, m303-deducciones-sector-2-rectification-cuota, m303-deducciones-sector-2-total, m303-exonerado-390-79, m303-exonerado-390-80, m303-exonerado-390-81, m303-exonerado-390-83, m303-exonerado-390-84, m303-exonerado-390-86, m303-exonerado-390-88 to m303-exonerado-390-99, m303-exonerado-390-107, m303-exonerado-390-125 to m303-exonerado-390-128, m303-prorrata-actividad-fila-1 to -fila-5, each with -cnae, -operaciones-con-derecho, -operaciones-total, -porcentaje and -tipo.

- The reviewer persona could not be launched; the orchestrating session reviewed the design against the amended ADR. Merge-order rearrangement is built from the pre-migration rows and the predecessor declaration only. `additional_source_refs` follows the `alternate_bindings` naming pattern. Lineage claims are stripped on inherit. `inherited_from` is one typed statement-origin marker, derived from the existing label origins. Closed on its contract; the only gate failure was locale identity, which S64 fixed in the catalogue, so S17's live run re-proves the full gate once the registry loads again. The auto-commit captured the code. One migration test, whose premise was an edition-keyed 131 binding that S15 removed, needs restating in S18.
