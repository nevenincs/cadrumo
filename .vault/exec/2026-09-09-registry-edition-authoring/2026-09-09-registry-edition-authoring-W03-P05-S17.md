---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:e0d742b0aca70aafe1dec4308bef310b7cfd21ab21dc577ed9e7587df550ec6e'
step_id: 'S17'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [L | opus-medium] Migrate modelo 303 end to end as the pilot: lift its restatement, author its successor editions as deltas, and prove it. Richest instrumentation in the corpus, so a mistake is cheapest to see here. Proof: round-trip equality, export bytes unchanged, delta-minimality clean for 303.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303`

## Changes

- `A` `dev/registry/edition_delta_migration.py`
- `A` `dev/registry/tests/test_edition_delta_migration.py`
- `verify:` `uv run --no-sync pytest -n 0 dev/registry/tests/test_edition_delta_migration.py` -> `pass` (10 passed)
- `verify:` `uv run --no-sync pytest -n 0 src/cadrumo/domain/calculations/registry/tests/test_revision_edition_round_trip.py dev/registry/tests/test_delta_minimality.py` -> `pass` (76 passed)
- `verify:` `uv run --no-sync ruff check` and `ruff format --check` on both files -> `pass`

## Notes

Skipped work: dry run only. Nothing was written under `modelos/303` or any `export/` tree, no `_MIGRATIONS` entry was added, and the Step stays open. The input was modelo 303 at HEAD `2604ddaf21`, read by `git archive` into a temporary registry, because the live `export/` tree was being rewritten at the time.

Per-edition results (`--declare-blocked-roots`):

| edition | basis | rows before | stated after | inherited | lifted row source_refs | lifted constraint source_refs | lifted constraint orden legal_refs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | first (root) | 184 | 184 | 0 | 0 (tie 88/88, no default) | 0 | 5 |
| 2023 | blocked: row_order | 198 | 198 | 0 | 99 | 81 | 5 |
| 2024-hasta-08-y-2t | blocked: row_order | 199 | 199 | 0 | 100 | 81 | 5 |
| 2024-desde-09-y-3t | blocked: row_order | 207 | 207 | 0 | 108 | 81 | 5 |
| 2025 | adjacent to 2024-desde-09-y-3t | 207 | 105 | 102 | 8 | 81 | 5 |
| 2026-y-siguientes | blocked: row_order | 208 | 208 | 0 | 109 | 81 | 5 |

- No row's top-level `legal_refs` equal its edition's orden, so no row-level orden lift happened.
- In 2025, every one of the 105 stated rows passes the screen but is not exact: 97 differ in `source_refs` (they cite the design plus the procedure) and 8 differ in `continuidad_evidence` or `continuidad_origin`. The 79 comment lines that leave 2025 with its inherited rows are all present verbatim in 2024-desde-09-y-3t.
- Order diagnosis: 2022 to 2023 reorders shared rows because the fragments were restructured. The 2023 to 2024-hasta, 2024-hasta to 2024-desde, and 2025 to 2026 edges insert new rows mid-sequence, and the materialiser can only append. Across the corpus, 23 of 70 successor edges are order-expressible.

Proofs:

- Round-trip gate, staged tree against the unmigrated copy, the same way the planted-migration tests run it: the only finding is `export_unchecked` on 2025. Typed equality, row order and locale identity are clean for all six editions, and no bytes were compared. The CLI exits 1 without the flag (refused at 2023) and 1 with it (the gate finding blocks `--apply`).
- A 303 byte proof cannot run today. The gate's `EditionExportScenario` carries no prior-domiciliation election or product software identity, and the 303 export path refuses to run without them.
- Delta-minimality for 303: 971 `restated_unchanged` before. After, the screen reads materialised rows as stated and reports 207. Over stated rows only it reports 105, the not-exact rows above. So it is not clean.
- S42 pin `test_modelo_184_raw_boe_design_eras_are_hash_pinned_and_explicitly_not_mapped`: before, 5 of 5 pass on the live tree (exit 0). After, its assertions hold for all five eras over a registry holding migrated 303 plus 184 (exit 0).
- S54 `test_committed_m100_continuity_surface_for_1038_retirement_is_loaded`: passes before and after (exit 0). It has no teeth here, because no 303 edition retires a lineage and modelo 100 is not migrated. Retirement is exercised instead by a planted 303 retirement in the tests.
- S50: the left-pad resolver finds 656 exact tokens, 0 left-padded, 0 ambiguous, and 6 of 6 maps resolved, before and after. That check is vacuous for 303. Export-ref symmetry reports 0 findings before and after.
- Determinism: two runs write byte-identical trees (290 files). Idempotency: a re-run on the migrated tree is a no-op.
