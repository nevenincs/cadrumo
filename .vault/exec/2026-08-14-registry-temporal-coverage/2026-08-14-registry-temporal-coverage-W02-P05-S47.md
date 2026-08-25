---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f82e419196424bbeb041082fb568c379cac588df644e990730e86a6ae6ce1580'
step_id: 'S47'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Acquire and hash-pin Modelo 194 design authority for 2019 through 2022, preserve the 2023 and 2024 successors as distinct source eras, and constrain any open horizon to publication-backed evidence without promoting authority grade.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/194/`
- `src/cadrumo/_data/registry/aeat/legal/`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_194/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Acquire the official AEAT historical Modelo 194 design that identifies `Ejercicio 2019` through the canonical record-design corpus synchronizer.
- Register its immutable byte count and SHA-256, remove that now-represented URL from the historical-exclusion ledger, and recheck the corpus inventory.
- Split the single open revision into finite `2019`, `2023`, and `2024` applicability-grade revisions with the corresponding BOE amendment and commencement references.
- Refuse the unsupported 2020 through 2022 gap and the unacquired 2025-and-later horizon; retain manual casillas only and declare no export layout.
- Migrate the four locale catalogues with the canonical revision-move command and correct the three Spanish era labels through the locale authority.
- Add direct selection, source-window, source-hash, and mutation tests for the three published design eras.

## Outcome

Modelo 194 now has three and only three publication-backed design eras: 2019, 2023, and 2024. The 2019 binary is corpus-enrolled and source-catalogued with SHA-256 `792cd3ab3f1e94ce7afd62a6fa37710253aec7b801e3097ad27741f90a657d5a`. The existing 2023 and 2024 sources are each bounded to their named exercise, so selection refuses 2020 to 2022 and 2025 onward. Authority stays `applicability`; no layout or filing claim was added.

Verification completed:

- `uv run --no-sync python -m dev.corpus.sync_aeat_record_design_corpus` — `OK: 61 required official URLs and 58 manifests`.
- `uv run --no-sync python -m dev.locales move-revision 194 2019-y-siguientes 2019 2023 2024 --drop-undistributed --dry-run`, followed by the same command without `--dry-run` — 144 leaves written and 48 obsolete leaves released across four catalogues.
- `uv run --no-sync python -m dev.locales scaffold --check` — no locale drift.
- `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_modelo_187_188_194_registry.py -q` — 15 passed.

## Notes

The whole-corpus registration test still reports 39 unrelated legacy record-design binaries without source rows; its failure list contains no Modelo 194 path, which is now enrolled. That pre-existing fleet backlog is outside this step's bounded M194 change.
