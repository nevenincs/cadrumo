# M037 Historical AEAT-Sede Search Log

**Search date:** 2026-05-27
**Searcher:** Task #60 (D) — chore/eliminate-shims campaign
**Scope:** Exhaustive WebFetch search of AEAT Sede and BOE for M037 historical material
**Outcome:** PARTIAL — BOE suppression order captured; no Diseño de Registro found

---

## Background

Modelo 037 (Declaración censal simplificada) was created by Orden EHA/1274/2007 and
retired by Orden HAC/1526/2024 (BOE-A-2025-410, in force 3 Feb 2025). Functionality
was folded into Modelo 036. The domain layer enforces `authority.validate_modelo("037")`
raises RegistrySnapshotError — registry presence is structurally forbidden and must
remain so.

---

## URL Patterns Attempted

### Diseño de Registro (XLSX — all 404)

Pattern: `https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_01_99/archivos/DR037v{NN}.xlsx`

Versions v01 through v15 — all returned **404 Not Found**.

Alternate filename patterns also tried: `DR037.xlsx`, `DR_037.xlsx`, `DR037v1.xlsx`,
`DR037_v01.xlsx`, `DR037v01.pdf`, `DR037v02.pdf`, `DR037.pdf` — all **404**.

### AEAT Sede HTML pages (all 404)

- `https://sede.agenciatributaria.gob.es/Sede/iva/declaraciones-iva/modelo-037-declaracion-censal-simplificada.html` — **404**
- `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/guia-practica-cumplimentacion-modelo-censal-037/` — **404**
- `https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/presentacion-declaraciones-ayuda-tecnica/modelo-037/` — **404**
- `https://sede.agenciatributaria.gob.es/Sede/censos/declaracion-censal-inicio-baja-censo-empresarios/modelo-037-declaracion-censal-simplificada.html` — **404**
- `https://sede.agenciatributaria.gob.es/Sede/censos/modelo-037.html` — **404**
- `https://sede.agenciatributaria.gob.es/Sede/censos/declaracion-censal.html` — **404**
- `https://sede.agenciatributaria.gob.es/Sede/censos/declaracion-censal-inicio-baja-censo-empresarios.html` — **404**
- AEAT static PDF variants (mod_037.pdf, modelo_037.pdf, M037.pdf, 037.pdf) — all **404**

### AEAT ejercicios-anteriores disenos-registro (definitive absence)

The `ejercicios-anteriores` archive for modelos 01-99 was fetched and parsed:
`https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-01-99_.html`

The page lists 036 (multiple revisions) then jumps directly to 038. **M037 is absent
from the archive index entirely.** This confirms AEAT never published a Diseño de
Registro for M037 — the form was always used via the M036/AEAT portal flow without
a structured record-layout specification.

Current index page (`modelos-01-99.html`) also contains zero references to 037.

### BOE — suppression order (200, content captured)

- `https://www.boe.es/buscar/doc.php?id=BOE-A-2025-410` — **200 OK**

Full text captured to `files/BOE-A-2025-410-orden-hac-1526-2024-supresion-m037.txt`.

The text confirms:
- Orden HAC/1526/2024 suppresses M037 explicitly ("esta orden suprime el modelo 037
  de Declaración censal simplificada")
- Rationale: digitisation/assistance tools now allow M036 to serve all use-cases
  that justified M037's simplified form
- Entry into force: 3 February 2025
- Amends Orden EHA/1274/2007 by removing all M037 references

### BOE — creation order (not retrieved)

Orden EHA/1274/2007 (original M037 creation) was searched. The BOE search interface
returned no matching document for `BOE-A-2007-*` with "1274/2007" content. Several
candidate IDs (BOE-A-2007-8399, -8400, -9012, -9013) returned 200 but none contained
the EHA/1274/2007 order text. Full BOE full-text search was not attempted (would
require additional form submissions). The suppression order (captured above) quotes
the creation order extensively and confirms M037's original scope.

---

## Structural Verdict

**M037 historical Diseño de Registro: DOES NOT EXIST on AEAT Sede.**

The form was designed as a simplified census declaration accessible via the AEAT
portal UI — it never had a machine-readable Diseño de Registro file published to the
static file server. AEAT's ejercicios-anteriores archive confirms this: M036 has
multiple historical versions listed; M037 has none.

The BOE suppression order is the only durable AEAT-published material about M037
in a format retrievable from the web. It is captured here as historical evidence.

**Domain-enforced absence is the only correct state.** The manifest.json at
`corpus/aeat_official/disenos_registro/modelo_037/manifest.json` correctly records
`artefact_count: 0` with note "No matching official AEAT disenos-registro link was
found." This search corroborates that finding definitively.

---

## Files Captured

| File | Source | Content |
|------|--------|---------|
| `BOE-A-2025-410-orden-hac-1526-2024-supresion-m037.txt` | https://www.boe.es/buscar/doc.php?id=BOE-A-2025-410 | Full text of suppression order (24 KB) |

---

## Domain Invariant Status

The test `test_no_committed_modelo_037_toml_can_revive_active_support` and
`authority.validate_modelo("037")` raising `RegistrySnapshotError` remain correct
and must not be changed. No registry TOML for M037 should ever be created.
