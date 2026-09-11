---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:cee58f4c5cdfd8726522910828b12e0a743db640445da71a4b2b668ad338f8ca'
step_id: 'S63'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [M | opus-medium] Unblock the successor edges that fail for missing lineage rather than order: of 67 successor edges, 33 are blocked because a predecessor row carries no continuidad_id, 2 by a lineage withdrawn without a retirement record, and 1 by a lower authority grade (that one correctly stays full-copy). For each lineage-blocked edge, seed or ground the missing predecessor-row lineage through the existing seeder and rulings (seeded marked apart from grounded, no identity from a byte span or box number alone), and declare each real withdrawal as a retirement evolution grounded in the official design. Rows that cannot be grounded stay unresolved in the lineage ledger, never guessed. Proof: the migration script reports each unblocked edge as migratable, the lineage totality gate stays at zero uncovered and zero stale, and every edge still blocked is listed with its reason.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`

## Changes

- `M` `dev/registry/analysis/casilla_lineage_rulings.toml`
- `M` `dev/registry/analysis/casilla_lineage_ledger.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/341/revisions/2005-2015/casillas/cdecl.ejercicio__cwire.observaciones.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/341/revisions/2016-y-siguientes/revision.toml`
- `A` `src/cadrumo/_data/registry/aeat/modelos/341/revisions/2016-y-siguientes/casilla_continuidad_evolutions/0001-2005-2015-2016-y-siguientes-retired.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/casillas/civa.anual.repercutido.recargo.tipo-0-62.base.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/casillas/civa.anual.repercutido.recargo.tipo-0.base.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/casillas/civa.anual.repercutido.recargo.tipo-0.cuota.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/casillas/civa.anual.repercutido.recargo.tipo-0-26.base.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/casillas/civa.anual.repercutido.recargo.tipo-0-62.base.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/casillas/civa.anual.repercutido.recargo.tipo-0.base.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/casillas/civa.anual.repercutido.recargo.tipo-0.cuota.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/casillas/civa.anual.repercutido.recargo.tipo-1.base.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/casillas/civa.anual.repercutido.recargo.tipo-0-26.base.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/casillas/civa.anual.repercutido.recargo.tipo-0-62.base.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/casillas/civa.anual.repercutido.recargo.tipo-0.base.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/casillas/civa.anual.repercutido.recargo.tipo-0.cuota.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/casillas/civa.anual.repercutido.recargo.tipo-1.base.toml`
- `verify:` `python -m dev.registry.analysis.casilla_lineage_seed --apply` (re-run after all edits) -> `pass` (edited 0 rows, contradictions 0, ledger byte-stable)
- `verify:` `pytest -n 0 -m "(unit or integration) and not resident_service and not external_tool"` on the lineage totality gate, lineage seed, continuity integrity, capability continuity, continuity candidate facts, delta-minimality and materialisation entry point -> `pass` (66 passed)
- `verify:` migration planner over all 70 successor edges, plus the migration CLI dry run (no `--apply`) for 341 and 390 -> `pass` (see Notes)
- `verify:` same-instant fingerprint of all 128 revisions, live tree against live tree with these files at HEAD -> `pass` (only 341 2005-2015, 341 2016-y-siguientes, 390 2023, 390 2024 and 390 2025 differ)
- `verify:` `pytest dev/registry/tests/test_edition_delta_migration.py` -> `fail` (collection error, see Notes)

## Notes

Unblocked (migration planner basis `adjacent`, no blocked cause):

- 341 2005-2015 -> 2016-y-siguientes: three retirement evolutions. The 2005-2015 design (aeat-dr-341-2005-2015) prints Letras etiqueta at 14, C.C.C. at 130 and Observaciones at 270. The 2016 design (aeat-dr-341-2016) prints none of them. The three predecessor rows carry role-derived chain ids as the retirement's handle. The 2016 manifest's empty-family disposition for evolutions was removed, because the loader refuses a disposition beside content.
- 390 2023 -> 2024 and 2024 -> 2025: two grounded rulings covering 8 rows. The campo descriptions are identical across the three pinned designs, for example Recargo de equivalencia Tipo 0% Base imponible [663]. The seeder wrote the evidence loci, and nothing was seeded.

Gate on the staged migrations: 341 has only `export_unchecked` on 2016-y-siguientes. The CLI refuses 390, because its single-modelo copy leaves out 303, which 390 depends on. A scratch stage that kept 303 ran the real gate: only `export_unchecked` on 2022, 2024 and 2025, with typed equality, merge order and locale identity clean. In that stage 2024 inherits 323 rows and 2025 inherits 331.

Still blocked, with the reason:

- 100 (5 edges), 200 and 309 (3 edges): excluded modelos, outside the seeder's scope.
- 123: `06>12` is ruled grounded but cannot be localised, because the 2019-2023 design prints row 06 only as the formula campo `[03] + [05]`. Predecessor row 01 is discontinued and has no chain id.
- 131 2025 -> 2026: not a withdrawal. Orden HAC/1425/2025 Anexo II keeps the indices correctores that 2025 models. The 2026 edition left them out as a modelling slice.
- 151: 49 predecessor rows are absent from the successor, and the 2015-2022 design does not print 40 of the declared boxes. Four role_absent rows can only be located by a byte span.
- 180 (3 rows), 202 (11 per edge, 2 edges), 322 (22 per edge, 3 edges), 490 (2021 -> 2022-1t: 72; 2022-2t-4t -> 2023: 20), 604 (35) and 714 (24 per edge, 4 edges): no design line or record campo localises these rows, so a ruling would be refused as grounded_unlocalised.
- 220 2024 -> 2025: the successor declares 2 rows against 1983. This is incomplete authoring, not a withdrawal.
- 308 (2 edges): partial_stamp and contradicted rows, and the 2011-2015 design has no extract.
- 353: the 8 absent rows are product aggregate members that the design never printed, so no official-design retirement exists.
- 490 2022-1t -> 2022-2t-4t: 124 absent rows and 27 rows that cannot be localised.
- Blocked, but not by lineage (unchanged): 165 (lower_grade), 308 2009 (overlapping) and 390 2022 -> 2023 (row_order).

Persistent failures not caused by this Step:

- The migration module cannot be imported without the signed artifact, because its round-trip import reaches `export_draft`. The proofs ran through a scratch-only shim that routes `bundled_authority` to the dev-compiled sources and empties the category profiles built at import time.
- `src/cadrumo/domain/categories/registry.py` calls `frozenset.intersection` with `set` operands, which breaks collection of `test_edition_delta_migration.py`.
- `test_delta_target_publication.py` and `test_isolated_edition_staging.py` have 4 failures: modelo 210 and `_stage_isolated_edition` signature drift, in code another lane is editing under `dev/registry/pipeline`.

Regenerating the ledger also rewrote modelo 308's reason text, because a 308 design extract is now bundled, and reordered modelo 100's residual entries. The rows and categories are unchanged.

The reviewer persona could not be launched, so the orchestrating session reviewed the diff against the ADR.

- Grounded and seeded stay apart. The 390 rows carry `continuidad_origin = "grounded"` with evidence cited at the design line, and nothing is seeded.
- The three 341 chain ids sit on the first edition of their chain, so there is no predecessor for an origin to describe. They are authored handles, and each retirement evolution cites both pinned designs.
- No field was authored to pass a gate. The 131 withdrawal was correctly refused as a retirement.
- Independent re-run: the lineage, continuity, delta-minimality and materialisation suites -> `pass` (71 passed, exit 0).
