---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:5af3fe357f87c77b69192dd8a401f464eca9c0ba5779b8921020de9b13e36cff'
step_id: 'S17'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

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

Export bytes proof, closed after the first dry run:

- `A` `dev/registry/edition_export_scenarios.py` declares the 303 and 131 export scenarios with synthetic identities and facts from each edition's own resolvers. The migration command reads it; tests no longer supply scenarios.
- `A` `dev/registry/edition_round_trip.py` is the gate engine. It is no longer imported from a src test, and staged copies now carry the target modelo's dependency closure.
- The dry run on the live tree, without `--apply`, now exits 0 with `gate_findings=0`. It byte-compares 2023, 2024-hasta-08-y-2t, 2024-desde-09-y-3t, 2025 and 2026-y-siguientes, and every one is equal. Teeth: planting one changed character in the migrated 2025 resultados record yields exactly one content finding and one export_bytes finding.
- `verify:` `pytest dev/registry/tests/test_revision_edition_round_trip.py` -> `pass` (71 passed)
- `verify:` `pytest dev/registry/tests/test_edition_delta_migration.py` -> `pass`
- 2022, the root edition, cannot be exported: the export path refuses its layout with "regimen-simplificado projection record must repeat projection_rows". It is a root, so the gate does not require its bytes.
- The gate turns only a ValueError into a finding. A scenario that `build_draft` rejects (ModeloApplicationError) crashes the tool instead. This is an S18 hardening item.
- `test_m303_generated_envelope_proof.py` fails on the migrated-fact gate for an isolated authority, e.g. `lirpf-art-101:retencion-administrador-general`. That comes from another lane's in-flight fact-provider work, not from this Step.

Applied on the live tree:

- Once row order became expressible, every successor migrated adjacent. The inherited and stated rows per edition are: 2023, 165 inherited, 33 stated; 2024-hasta-08-y-2t, 192 and 7; 2024-desde-09-y-3t, 192 and 15; 2025, 201 and 6; 2026-y-siguientes, 196 and 12. 2022 stays the full-copy root.
- `M` `src/cadrumo/_data/registry/aeat/modelos/303` (46 files; no export tree touched)
- `M` `dev/registry/tests/test_revision_edition_round_trip.py` (the `_MIGRATIONS` baseline for 303 at `784c7cdd3e`, the last full-copy commit)
- `M` `dev/registry/tests/test_delta_minimality.py` (the live-corpus screen now names 131 but not 303, which restates nothing)
- `M` `src/cadrumo/_data/registry/authority/authority.json` (republished)
- `verify:` `python -m dev.registry.edition_delta_migration --modelo 303 --apply` -> `pass` (gate_findings=0; export bytes equal on all five successors; applied=True)
- `verify:` `python -m dev.registry.conformance integrity` -> `pass`
- `verify:` corpus round-trip gate for 303, 390 and 131 -> `pass` (3 passed)
- `verify:` delta-minimality, lineage totality and continuity integrity -> `pass` (25 passed)
- `verify:` `test_m303_did_account_wire_isolated_authority.py` -> `pass`

The reviewer persona could not be launched, so the orchestrating session reviewed the result against the ADR. Inheritance is keyed on lineage. Restatement is lifted to the edition, as `source_default` per edition. The loader infers no predecessor, because every edge is declared. The proof obligations hold: typed equality, merge order, locale identity and export bytes.
