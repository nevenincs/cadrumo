---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: "2026-05-27"
modified: '2026-05-27'
step_id: "S174"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W07.P33.S174

## Step

Ground M131 (IRPF pagos fraccionados modalidad estimacion objetiva — quarterly)
declaracion_pdf extraction profile against AEAT-published DR xlsx 2026 and instructions
HTML; determine printed-form layout verdict (line-start vs line-end box numbers); author
synthetic fixture 131/2024-1T.pdf; add structural gap test asserting zero casilla
extraction from the real profile on the synthetic fixture; retain
provisional_pending_specimen=true on all M131 extraction_profiles revisions.

## AEAT Material Accessed

**01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx** — Diseño de Registro
Modelo 131, Versión ejercicios 2026:
- Local corpus: `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_131/files/01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx`
- Shared strings [65]-[78] confirm bracket [NN] casilla notation throughout:
  - string 65: "Liquidación (3) - I. Activ. económicas estimac. objetiva - Pago fraccionado previo: suma de resultados [02]"
  - string 66: "Liquidación (3) - I. Activ. económicas estimac. objetiva - Suma de rendimientos netos [01]"
  - string 73: "Liquidación (3) - IV. Total liquidación - Diferencia [10]"
  - string 78: "Liquidación (3) - IV. Total liquidación - Resultado de la declaración [15]"
- All 15 casilla field names end with `[NN]` — box number is a trailing bracket reference,
  not a line-start anchor prefix

**modelo-131-instrucciones.html** — AEAT printed-form instructions:
- Local corpus: `src/aeat/_data/corpus/aeat_official/instructions/modelo_131/files/modelo-131-instrucciones.html`
- All 15 sections carry headings in the form "Casilla NN." (e.g. "Casilla 01.", "Casilla 15.")
- Box numbers appear as section headings in explanatory text, not as printed-form line-start
  anchors; this is consistent with a tabular dot-fill layout on the physical form

**M130 corpus empirical evidence (15 PDFs, 2021-2024):**
- Sister form: M130 IRPF pago fraccionado estimacion directa, same AEAT quarterly IRPF series
- All 15 M130 corpus PDFs confirmed coverage=0 under numeric_casilla strategy
- M130 layout: line-end box numbers with dot-fill (e.g. "Suma de rendimientos netos .... 01  5.000,00")
- M131 shares the same AEAT form generation system and tabular layout convention

## Layout Verdict

**GAP-DOCUMENTED** — M131 printed form uses the same line-end box-number tabular layout as
M130 (both AEAT IRPF quarterly pago-fraccionado forms, same AEAT form-generation system).
The `numeric_casilla` strategy requires box numbers at LINE START (`^\s*NN\b...<amount>`);
M131's bracket [NN] notation and dot-fill tabular format places box numbers at LINE END.
Coverage will always be 0 for any real M131 declaracion PDF under this strategy.

Three independent evidence lines confirm the verdict:
1. AEAT DR xlsx 2026 shared-strings [65]-[78]: bracket [NN] trailing notation on all 15 fields
2. AEAT instructions HTML: "Casilla NN." section headings (reference format, not line-start)
3. M130 empirical corpus (15 PDFs): confirmed line-end layout for the same IRPF form series

## Profile State

All M131 extraction_profiles TOML revisions retain `provisional_pending_specimen = true`.
No flag flip — a real M131 declaracion PDF corpus is needed to confirm fixture fidelity
before the flag can move to `corpus_round_trip_verified`.

The extraction profile itself is unchanged:
```toml
[[revisions."2026".extraction_profiles]]
id = "modelo-131-declaracion-pdf"
surface = "declaracion_pdf"
artefact_kind = "declaracion"
accepted_artefact_kinds = ["declaration_pdf"]
parser = "aeat.adapters.inbound.declaracion.parse_declaracion"
...
confidence = "strict"
provisional_pending_specimen = true
min_coverage = "1"
failure_semantics = "fail_hard"
```

## Fixture

`src/aeat/tests/fixtures/justificantes/131/2024-1T.pdf` — authored via `_generate.py`
`_draw_modelo_131()` function. Prints line-end box number tabular layout:

```
Agencia Tributaria
Pago fraccionado estimacion objetiva IRPF Modelo 131
NIF: Y0000001S
Apellidos y nombre: DEMO AUTONOMO EO
Ejercicio: 2026 Periodo: 1T
Suma de rendimientos netos ........................ 01 5.000,00
Pago fraccionado previo por datos-base .............. 02 100,00
Volumen de ventas o ingresos sin datos-base ......... 03 0,00
Pago fraccionado previo sin datos-base .............. 04 0,00
Volumen de ingresos agrarios del trimestre .......... 05 0,00
Pago fraccionado previo agrario ..................... 06 0,00
Suma de pagos fraccionados previos .................. 07 100,00
Retenciones e ingresos a cuenta ..................... 08 0,00
Minoracion por rendimientos act. economicas ......... 09 0,00
Diferencia .......................................... 10 100,00
Resultados negativos de trimestres anteriores ....... 11 0,00
Pago de prestamos para vivienda habitual ............ 12 0,00
Total ............................................... 13 100,00
Resultado a ingresar de autoliquidaciones anteriores  14 0,00
Resultado de la declaracion ......................... 15 100,00
Ejemplar para el obligado tributario
```

Note: `ejercicio="2026"` in fixture content (not 2024) because the `declaracion_pdf`
extraction profile only exists on the 2026 revision; the filename `2024-1T.pdf` follows
corpus naming convention for the fiscal period.

## Test Result

`test_parser_modelo_131_numeric_casilla_profile_gap` — PASSED.

Gap documented:
- `parse_declaracion(_MODELO_131_SYNTHETIC_FIXTURE, modelo_override="131", año_override=2026, period_override="1T")`
- Raises: `DeclaracionParseError: Falló la extracción de la declaración con el perfil modelo-131-declaracion-pdf: missing=01,02,03,04,05,06,07,08,09,10,11,12,13,14,15; coverage=0`

## Flag State

M131 → **GAP-DOCUMENTED** — `provisional_pending_specimen = true` retained on all revisions.
No round-trip verification is possible without real M131 declaracion PDFs in the corpus.
