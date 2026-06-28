---
step_id: S375
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: "2026-05-27"
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
status: closed
---

# W12.P63.S375 — M037 historical AEAT-Sede corpus search

## Action performed

Exhaustive WebFetch search of AEAT Sede and BOE for retired Modelo 037 (Declaración
censal simplificada) historical material per Task #60 (D).

## URL results

### DR037 Diseño de Registro XLSX (v01–v15)

All 15 versioned URLs at pattern
`https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_01_99/archivos/DR037v{NN}.xlsx`
returned **404**. Alternate filename patterns (DR037.xlsx, DR037.pdf, etc.) also **404**.

### AEAT Sede HTML pages

All attempted census and IVA section URLs for M037 returned **404**:
- modelo-037-declaracion-censal-simplificada.html
- guia-practica-cumplimentacion-modelo-censal-037/
- consultas-informaticas/.../modelo-037/
- censos/modelo-037.html
- censos/declaracion-censal-inicio-baja-censo-empresarios/modelo-037-*.html

### AEAT ejercicios-anteriores disenos-registro (definitive)

Fetched and parsed `modelos-01-99_.html`. The page lists M036 (multiple revisions)
then jumps to M038. **M037 is absent** — no historical Diseño de Registro was ever
published by AEAT.

### BOE suppression order — **200 OK, content captured**

`https://www.boe.es/buscar/doc.php?id=BOE-A-2025-410` (Orden HAC/1526/2024) returned
200. Full text (24 KB) saved to
`src/aeat/_data/corpus/aeat_official/historical_retired_modelos/modelo_037/files/BOE-A-2025-410-orden-hac-1526-2024-supresion-m037.txt`.

Text confirms explicit suppression language: "esta orden suprime el modelo 037 de
Declaración censal simplificada", rationale being that M036 with digital assistance
tools now serves all simplified-census use-cases.

## Artefacts produced

- `src/aeat/_data/corpus/aeat_official/historical_retired_modelos/modelo_037/files/BOE-A-2025-410-orden-hac-1526-2024-supresion-m037.txt`
- `src/aeat/_data/corpus/aeat_official/historical_retired_modelos/modelo_037/SEARCH_LOG.md`

## Structural verdict

**M037 Diseño de Registro: DOES NOT EXIST on AEAT Sede.** The form never had a
machine-readable record-layout specification. Only the BOE suppression order exists
as AEAT-published material.

Domain-enforced absence (`authority.validate_modelo("037")` raises
`RegistrySnapshotError`) is confirmed correct and must not be changed. No registry
TOML for M037 should ever be created.

## Domain invariants

No production code was modified. Suite integrity unchanged.
