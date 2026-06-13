---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W07.P27.S165'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# declaracion-extraction-architecture W07.P27.S165

Tagged every `declaracion_pdf` extraction profile with its ground-truth verification state. Eight profiles confirmed as VERIFIED receive `corpus_round_trip_verified = true`; two corpus-gap profiles receive `provisional_pending_specimen = true`; twelve already-provisional profiles are unchanged.

## Files modified

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/190.toml`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/390.toml`
- `src/aeat/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/extraction_profiles/0005-extraction_profiles.toml`
- `src/aeat/_data/registry/aeat/modelos/130.toml`

## Ground-truth classification

VERIFIED (`corpus_round_trip_verified = true`):
- M100 2021, 2022, 2023: 19 `named_label` casillas each; real-corpus round-trip against 3-PDF corpus confirmed in `test_parser_boundary.py`
- M190 2024-y-siguientes: 3 `named_label` casillas; 1-PDF corpus round-trip confirmed
- M303 2009-y-siguientes: 4 casillas; 15-PDF corpus (combined across two templates)
- M303 2023-y-siguientes: 12 casillas; confirmed
- M390 2010-y-siguientes: 6 `named_label` casillas; 2-PDF corpus confirmed

CORPUS-GAP (`provisional_pending_specimen = true` added):
- M111: corpus exists at `justificantes/111/`; `numeric_casilla` strategy defeated by line-end box-number merging; extraction structurally fails on all 4 corpus PDFs
- M130: corpus exists at `justificantes/130/`; `numeric_casilla` strategy defeated by detached value blocks; coverage = 0 on all 15 corpus PDFs

NO-FIXTURE-ALREADY-PROVISIONAL (unchanged):
- M036, M115, M123 (×2), M131, M184, M193, M232 (×2), M347, M349, M720, M840

## Verification

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py test_provisional_specimen_gate.py test_corpus_round_trip_gate.py -q` — 52 passed, 0 failed.

## Commit

`cfc3ceb93`
