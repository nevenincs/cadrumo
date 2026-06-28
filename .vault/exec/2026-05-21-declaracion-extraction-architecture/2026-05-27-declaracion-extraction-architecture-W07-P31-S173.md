---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: "2026-05-27"
modified: '2026-05-27'
step_id: "S173"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W07.P31.S173

## Step

Ground M369 esquema-union declaracion_pdf profile: update label_patterns from registry
self-refs to AEAT-grounded 'Ejercicio:' and 'Periodo:'; save 5 AEAT corpus files;
author synthetic fixture 369/2024-1T.pdf; add round-trip test; flip
provisional_pending_specimen to corpus_round_trip_verified.

## AEAT Material Accessed

**DR369e21.xlsx** — Diseño de Registro Modelo 369, Versión 1.1:
- URL: https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_300_399/archivos_21/DR369e21.xlsx
- Fetched: 2026-05-27
- Sheet T36904 (Union scheme), row 14: "2. Ejercicio y período. Ejercicio"
- Sheet T36904, row 16: "2. Ejercicio y período. Periodo"

**AEAT online manual "Presentación régimen de la Unión", sections 1-2, 8-9:**
- Section 2 URL: https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-ayuda-presentacion/modelo-369/presentacion-regimen-union/2-ejercicio-periodo.html
- Section 2 heading: "2. Ejercicio y periodo"
- Section 2 instruction text: "Consignar el ejercicio y el período (primer trimestre, segundo trimestre, tercer trimestre, cuarto trimestre)"
- Fetched: 2026-05-27

**Descripcion_PresentacionFichero369_v1.pdf** — File submission description:
- URL: https://sede.agenciatributaria.gob.es/static_files/Sede/Consultas_Inf/Presentacion_declaraciones/IVA_mensuales_trimestrales/Modelo_369/Descripcion_PresentacionFichero369_v1.pdf
- Fetched: 2026-05-27
- Confirms M369 is an online-only form; no printed-form instructions PDF exists

## Per-Casilla Grounding Evidence

### decl.ejercicio

Previous pattern (registry self-reference — NOT grounded):
  `'Ejercicio\s+al\s+que\s+se\s+refiere\s+la\s+autoliquidaci[oó]n'`
  Source: registry casilla label field only — not AEAT-published form text.

Updated pattern (AEAT-grounded):
  `'Ejercicio:'`

AEAT grounding:
- DR369e21.xlsx sheet T36904 row 14: "2. Ejercicio y período. Ejercicio"
- AEAT manual section 2 heading: "2. Ejercicio y periodo"
- BOE HAC/610/2021 art. 2: "Ejercicio al que corresponde la presentación"
  (https://www.boe.es/buscar/act.php?id=BOE-A-2021-10161)

The "Ejercicio:" label is derived from the AEAT-published field vocabulary in the DR
field description and is the shortest canonical form of the AEAT-published term.

### decl.periodo

Previous pattern (registry self-reference — NOT grounded):
  `'Per[ií]odo\s+de\s+la\s+declaraci[oó]n'`
  Source: registry casilla label field only — not AEAT-published form text.

Updated pattern (AEAT-grounded):
  `'Per[ií]odo:'`

AEAT grounding:
- DR369e21.xlsx sheet T36904 row 16: "2. Ejercicio y período. Periodo"
- AEAT manual section 2 heading: "2. Ejercicio y periodo"
  (heading explicitly names "periodo" as a field in this section)

## Profile Shape

```toml
[[revisions."esquema-union".extraction_profiles]]
id = "modelo-369-union-declaracion-pdf"
surface = "declaracion_pdf"
artefact_kind = "declaration_pdf"
target_casillas = [
    {casilla_id = "decl.ejercicio", match_strategy = "named_label", value_kind = "amount",
     label_pattern = 'Ejercicio:'},
    {casilla_id = "decl.periodo", match_strategy = "named_label", value_kind = "text",
     label_pattern = 'Per[ií]odo:'},
]
corpus_round_trip_verified = true
```

## Fixture

`src/aeat/tests/fixtures/justificantes/369/2024-1T.pdf` — authored via
`_generate.py` `_draw_modelo_369()` function. Prints:
```
Agencia Tributaria
Autoliquidacion regimenes especiales OSS  Modelo 369
NIF: Y0000001S
Razon social: DEMO EMPRESA SL
Ejercicio: 2024
Periodo: 1T
Ejemplar para el obligado tributario
```

## Test Result

`test_parser_extracts_modelo_369_synthetic_fixture_targets` — PASSED.

Round-trip verified:
- `decl.ejercicio` → `Decimal('2024')` (extracted from "Ejercicio: 2024")
- `decl.periodo` → `'1T'` (extracted from "Periodo: 1T")

## Flag State

M369 PROVISIONAL → GROUNDED (`corpus_round_trip_verified = true`)

## Corpus Files Saved

- `src/aeat/_data/corpus/aeat_official/instructions/modelo_369/files/1-declarante.html`
- `src/aeat/_data/corpus/aeat_official/instructions/modelo_369/files/2-ejercicio-periodo.html`
- `src/aeat/_data/corpus/aeat_official/instructions/modelo_369/files/8-resultado-autoliquidacion.html`
- `src/aeat/_data/corpus/aeat_official/instructions/modelo_369/files/9-tipo-pago.html`
- `src/aeat/_data/corpus/aeat_official/instructions/modelo_369/files/Descripcion_PresentacionFichero369_v1.pdf`
