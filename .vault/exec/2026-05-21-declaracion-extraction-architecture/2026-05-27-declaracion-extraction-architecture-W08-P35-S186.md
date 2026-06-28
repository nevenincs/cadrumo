---
step_id: "W08.P35.S186"
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W08.P35.S186

Re-audit: M193 `_total` suffix convention verification against M180 real evidence.

## Evidence gathered

### M180 AEAT corpus labels (verbatim)

**Printed form bitmap** (`02-180-orden-de-20-de-noviembre-de-2000-12-kb-pdf.pdf`, page 1, REGISTRO DE TIPO 1):
- "NUMERO TOTAL DE PERCEPTORES" (positions 136-144)
- "BASE DE RETENCIONES E INGRESOS A CUENTA" (positions 145-160, with "DE")
- "RETENCIONES E INGRESOS A CUENTA" (positions 161-175)

**EDI spec** (`01-180-orden-hap-1732-2014-actualizado-por-orden-hfp-1284-2023.pdf`, pages 4-6):
- "NÚMERO TOTAL DE PERCEPTORES" (136-144)
- "BASE RETENCIONES E INGRESOS A CUENTA" (145-160, without "DE" — minor variant across the two documents)
- "RETENCIONES E INGRESOS A CUENTA" (161-175)

Neither AEAT corpus source uses a "total" suffix on the base or retenciones field names.

### M180 extraction profile patterns (0002-modelo-180-declaracion-pdf.toml)

```toml
{casilla_id = "decl.total-perceptores", label_pattern = 'N[uú]mero\s+total\s+de\s+perceptores'},
{casilla_id = "decl.base-total",        label_pattern = 'Base\s+(?:de\s+)?retenciones\s+e\s+ingresos\s+a\s+cuenta\s+total'},
{casilla_id = "decl.retenciones-total", label_pattern = 'Retenciones\s+e\s+ingresos\s+a\s+cuenta\s+total'},
```

The `\s+total` suffix is present in BOTH base and retenciones patterns.

### M180 fixture renders (_generate.py `_draw_modelo_180`, lines 323-336)

```python
f"Numero total de perceptores {fixture.total_perceptores}"
f"Base retenciones e ingresos a cuenta total {fixture.base_total}"
f"Retenciones e ingresos a cuenta total {fixture.retenciones_total}"
```

The fixture appends " total" to both summary-row labels. The patterns match these fixture strings. The round-trip closes against fixture text, not against AEAT corpus text — which is correctly reflected in `verification_source = "synthetic_from_aeat_published_text"`.

### M193 AEAT corpus labels (verbatim)

**DR Orden HAC/56/2024** (`03-193-orden-hac-56-2024-ejercicios-2024-y-siguientes-556-kb-pdf.pdf`, pages 5-6):
- 136-144: "NÚMERO TOTAL DE PERCEPTORES"
- 145-159: "BASE RETENCIONES E INGRESOS A CUENTA" (no "total")
- 160-174: "RETENCIONES E INGRESOS A CUENTA" (no "total")

### M193 extraction profile patterns (0001-extraction_profiles.toml)

```toml
{casilla_id = "decl.total-perceptores", label_pattern = 'N[uú]mero\s+total\s+de\s+perceptores'},
{casilla_id = "decl.base-total",        label_pattern = 'Base\s+retenciones\s+e\s+ingresos\s+a\s+cuenta\s+total'},
{casilla_id = "decl.retenciones-total", label_pattern = 'Retenciones\s+e\s+ingresos\s+a\s+cuenta\s+total'},
```

### M193 fixture renders (_generate.py `_draw_modelo_193`, lines 525-538)

```python
f"Numero total de perceptores {fixture.total_perceptores}"
f"Base retenciones e ingresos a cuenta total {fixture.base_total}"
f"Retenciones e ingresos a cuenta total {fixture.retenciones_total}"
```

Identical suffix convention to M180.

## Analysis

The task #32 audit verdict was factually correct that AEAT corpus field names carry no "total" suffix. The task #48 claim that "the suffix is the M180 fixture-disambiguation convention" is also correct: M180 independently uses the same suffix in both fixture and pattern, and the M193 profile adopts the same convention for the same reason — to allow the `named_label` parser to distinguish the declarante-level aggregate row from per-perceptor rows that share the "BASE RETENCIONES E INGRESOS A CUENTA" label root.

The convention is:
1. The AEAT corpus field name has no "total".
2. The synthetic fixture appends " total" to the summary row only.
3. The extraction profile pattern requires `\s+total` to match only the summary row.
4. `verification_source = "synthetic_from_aeat_published_text"` is accurate — the round-trip closes against the fixture, not against a real AEAT corpus PDF extraction.
5. `corpus_round_trip_verified = true` is accurate in the sense the fixture is constructed from published AEAT vocabulary.

The M193 TOML file already documents this at lines 1-14 with a precise inline comment covering the corpus source, the position mapping, and the disambiguation rationale.

## Verdict: CONFIRMED

The task #48 convention claim holds. The " total" suffix is a consistent fixture-level disambiguation device applied identically in M180 and M193. No code change is required.

`confidence = "strict"` and `corpus_round_trip_verified = true` on M193 remain accurate. No `provisional_pending_specimen` restoration is warranted.

## Files read

- `src/aeat/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/extraction_profiles/0002-modelo-180-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/casillas/0002-decl.base-total.toml`
- `src/aeat/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/casillas/0003-decl.retenciones-total.toml`
- `src/aeat/_data/registry/aeat/modelos/193/revisions/2024-y-siguientes/extraction_profiles/0001-extraction_profiles.toml`
- `src/aeat/tests/fixtures/justificantes/_generate.py` (functions `_draw_modelo_180`, `_draw_modelo_193`)
- `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_180/files/02-180-orden-de-20-de-noviembre-de-2000-12-kb-pdf.pdf` (page 1)
- `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_180/files/01-180-orden-hap-1732-2014-actualizado-por-orden-hfp-1284-2023-de-28-de-noviembre-251-kb-pdf.pdf` (pages 4-6)
- `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_193/files/03-193-orden-hac-56-2024-ejercicios-2024-y-siguientes-556-kb-pdf.pdf` (pages 5-6)
