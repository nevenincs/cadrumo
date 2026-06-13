---
step_id: S180
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
---

# declaracion-extraction-architecture W07.P32.S180

## Action

Ground M115 declaracion_pdf extraction: convert numeric_casilla to named_label,
generate synthetic fixture, add round-trip test, fix provisional specimen gate test.

## Scope

- `src/aeat/_data/registry/aeat/modelos/115/revisions/2019-y-siguientes/extraction_profiles/0001-extraction_profiles.toml`
- `src/aeat/tests/fixtures/justificantes/115/2024-1T.pdf`
- `src/aeat/tests/fixtures/justificantes/_generate.py`
- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`
- `src/aeat/domain/calculations/registry/test_provisional_specimen_gate.py`

## Outcome

### Layout verdict

M115 (Modelo 115 retenciones sobre rendimientos del capital inmobiliario) printed
form uses the same two-column table layout as M111 — box numbers appear at LINE-END
inside bordered table cells, not at LINE-START. The `numeric_casilla` match strategy
(regex anchored at `^\s*<N>\b`) structurally cannot match any casilla from a real
AEAT M115 PDF.

Grounding source: AEAT DR XLS sheet "DR 11501" rows 16-20 (Windows-1252 decoded),
file `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_115/files/01-115-orden-eha-3435-2007-ejercicios-2019-y-siguientes-actualizado-febrero-2019-172-kb-xls.xls`.

### Extraction profile conversion

Converted `modelo-115-declaracion-pdf` from `numeric_casilla` to `named_label`
strategy. Five casillas mapped to DR XLS field descriptions:

- `01`: `N[uú]mero\s+(?:de\s+)?perceptores`
- `02`: `Base\s+(?:de\s+)?retenciones\s+e\s+ingresos\s+a\s+cuenta`
- `03`: `Retenciones\s+e\s+ingresos\s+a\s+cuenta(?!\s+Base)`
- `04`: `Resultado\s+(?:de\s+)?anteriores\s+(?:declaraciones|autoliquidaciones)`
- `05`: `Resultado\s+a\s+ingresar`

Replaced `provisional_pending_specimen = true` with `corpus_round_trip_verified = true`.

### Synthetic fixture

Generated `src/aeat/tests/fixtures/justificantes/115/2024-1T.pdf` via reportlab.
Fixture title deliberately avoids "Retenciones..." prefix to prevent casilla 03
named_label collision. pdfplumber round-trip verified: all five labels extract
correct Spanish-formatted amounts.

### Round-trip test

Added `test_parser_extracts_modelo_115_synthetic_fixture_targets` to
`test_parser_boundary.py`. Asserts all five casilla_ids extracted with correct
Decimal values derived from fixture constants (non-tautological: values are
grounded in the fixture generator, not copied from a test run).

### Provisional specimen gate fix

`test_gate_fires_via_production_path` was stale: M184 now has `corpus_round_trip_verified = true`
and a fixture at `justificantes/184/2024-0A.pdf`, so overriding `provisional_pending_specimen`
to False no longer triggered the gate. Renamed test to `test_gate_fires_no_fixture_no_flag`,
switched to M130 with an injected empty `tmp_path` corpus root (consistent with the
pattern used by the three other gate tests). Production-path corpus derivation is
already covered by `test_corpus_root_derived_from_bundled_path`.

## Gate result

```
127 passed in 478.91s
```

All target modules pass: `declaracion/`, `test_provisional_specimen_gate.py`,
`test_corpus_round_trip_gate.py`, `test_modelo_parity_coverage.py`.
