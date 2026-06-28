---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S172'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# `declaracion-extraction-architecture` `W07.P29.S172`

Ground Modelo 720 declaracion_pdf extraction profile from AEAT-published Sede material.

## Files Modified

- `src/aeat/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes/extraction_profiles/0001-extraction_profiles.toml`
- `src/aeat/tests/fixtures/justificantes/_generate.py`
- `src/aeat/tests/fixtures/justificantes/720/2024-0A.pdf`
- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`

## Description

Two PROVISIONAL `declaracion_pdf` profile targets for M720 were audited against
AEAT-published sources:

**`decl.ejercicio`** — GROUNDED.  Pattern
`'Ejercicio\s+al\s+que\s+se\s+refiere\s+la\s+informaci[oó]n'` is linguistically
correct.  Evidence chain: (1) AEAT-published `modelo_720.pdf` (diseño de registro),
downloaded 2026-05-27, positions 5-8 = EJERCICIO; (2) Orden HAP/72/2013 Art. 7:
"al que se refiera la información a suministrar" — M720 is a declaración informativa
and uses "información" throughout; (3) `aeat-dr-720` casilla label: "Ejercicio al que
se refiere la informacion".

**`decl.tipo-declaracion`** — REMOVED.  Pattern `'Tipo\s+de\s+declaraci[oó]n'` is
not groundable.  Record-type-1 positions 121-122 are "DECLARACIÓN COMPLEMENTARIA O
SUSTITUTIVA" — two separate single-character flags, not a printed label+value pair.
No AEAT-published source uses "Tipo de declaración" as a labeled field for M720.

Profile transitioned from `provisional_pending_specimen = true` /
`confidence = "review_required"` to `corpus_round_trip_verified = true` /
`confidence = "strict"`.

Synthetic fixture `720/2024-0A.pdf` added via `_generate.py`.  The fixture prints
`"Ejercicio al que se refiere la informacion 2024"` so the named_label parser can
locate and extract the ejercicio value.

Round-trip test `test_parser_extracts_modelo_720_synthetic_fixture_targets` added
to `test_parser_boundary.py`.  The test asserts only `decl.ejercicio` is extracted
(not `decl.tipo-declaracion`) and that `values["decl.ejercicio"] == Decimal("2024")`.

## Tests

- `uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/test_parser_boundary.py::test_parser_extracts_modelo_720_synthetic_fixture_targets src/aeat/domain/calculations/registry/test_provisional_specimen_gate.py src/aeat/domain/calculations/registry/test_corpus_round_trip_gate.py src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py -q` — 13 passed
- `uv run --no-sync ruff check` — all checks passed
