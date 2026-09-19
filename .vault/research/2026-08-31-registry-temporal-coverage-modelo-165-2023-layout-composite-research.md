---
tags:
  - '#research'
  - '#registry-temporal-coverage'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:23c41ab99af60807b881965418220fda99a4000f7f4308998a7e1361ef290370'
related:
  - "[[2026-08-15-registry-temporal-coverage-acquisition-worklist-research]]"
  - "[[2026-08-27-registry-temporal-coverage-design-authority-declaration-adr]]"
---
# `registry-temporal-coverage` research: `Modelo 165 2023 layout composite`

The official record establishes the Modelo 165 2023--2025 layout era, but the presently bundled AEAT URL is mutable and now serves an `Ejercicio 2026` PDF. The evidence supports either a narrowly defined, provenance-preserving composite representation or continued applicability-only treatment until an immutable AEAT 2023 binary is recovered; it does not support backdating the 2026 design.

## Findings

### The 2023 change and its first applicable ejercicio are official and exact

`BOE-A-2023-24412`, Article 13, adds Type-1 `EMPRESA EMERGENTE` at position 184 and changes the blank range to 185--500. Its final provision makes the order applicable for the first time to informative declarations for ejercicio 2023, presented in 2024. `https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-24412`

### The predecessor design supplies the unchanged geometry

`BOE-A-2016-11251` establishes the immediate preceding Type-1 design with signed `IMPORTE FONDOS PROPIOS` at 168--183 and blanks from 184. The original Modelo 165 order's subsequent-reference record lists the 2016 and 2023 amendments, with no later 2024 or 2025 geometry amendment. Therefore the evidenced 2023--2025 Type-1 geometry is the 2016 design plus the exact 2023 delta; Type 2 is unaffected. `https://www.boe.es/buscar/doc.php?id=BOE-A-2016-11251` `https://www.boe.es/diario_boe/txt.php?id=BOE-A-2013-13798`

### The current AEAT URL cannot be used as the historical binary

The repository's downloaded PDF from the URL named `DR_Mod_165_2023.pdf` is headed `Ejercicio 2026`. Existing tests correctly keep it out of the 2023--2025 interval. This is a source-stability problem, not a basis to reinterpret the later artefact as historical authority. `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_165/files/01-165-diseno-de-registro-actualizado-en-2023.pdf.extracted.md` `src/cadrumo/domain/calculations/registry/tests/test_modelo_165_historical_layout_authority.py`

### The admissible representation needs a decision

The accepted design-authority ADR permits raw BOE material as provenance-only and prevents it from silently becoming an executable layout map. A composite derived from the existing pinned 2016 AEAT design plus the pinable BOE 2023 change is neither directly authorized nor ruled out. The decision must either admit that narrowly sourced representation with both provenance inputs or retain applicability-only treatment pending a recoverable immutable AEAT 2023 binary.

## Sources

- `https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-24412`
- `https://www.boe.es/buscar/doc.php?id=BOE-A-2016-11251`
- `https://www.boe.es/diario_boe/txt.php?id=BOE-A-2013-13798`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_165/files/01-165-diseno-de-registro-actualizado-en-2023.pdf.extracted.md`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_165_historical_layout_authority.py`
