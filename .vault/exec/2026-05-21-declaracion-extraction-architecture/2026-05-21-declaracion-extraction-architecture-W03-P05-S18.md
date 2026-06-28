---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S18'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# `declaracion-extraction-architecture` `W03.P05.S18`

Scoped discovery sweep of AEAT Diseño corpus and casilla registry data for M303, M180, and M190. Source-gap findings documented; no schema-tweak Steps added (see findings below).

- Swept: `src/aeat/_data/registry/aeat/modelos/303.toml`
- Swept: `src/aeat/_data/registry/aeat/modelos/180/` (manifest + revisions)
- Swept: `src/aeat/_data/registry/aeat/modelos/190.toml`
- Swept: `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_303/`
- Swept: `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_180/`
- Swept: `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_190/`

## Description

### M303 — source gap: casilla ID / form number mismatch

The M303 registry uses semantic slug IDs for all casillas (`iva.repercutido.general`, `iva.cuota-devengada-total`, etc.). The printed declaración form uses numeric boxes `01`–`110`. None of the semantic slug IDs match the printed box numbers. The `numeric_casilla` match strategy anchors on `re.escape(casilla_id)` at line start; since no casilla ID in the M303 registry equals a printed form number, no `numeric_casilla` extraction profile can be authored for M303 without adding numeric casilla registry entries (like M111's `id = "01"` .. `id = "30"`).

The four casillas `iva.compensacion-pendiente-periodos-anteriores`, `iva.compensacion-aplicada-periodo`, `iva.compensacion-pendiente-periodos-posteriores`, and `iva.resultado` carry `number = "110"`, `"78"`, `"87"`, `"69"` respectively — these numbers ARE printed on the form, but the casilla IDs are still the slugs, not the numbers. The referential validator requires `target_casillas[*].casilla_id ∈ revision.casilla_ids`; these slugs never appear in any printed line.

**Verdict:** A working `numeric_casilla` declaracion_pdf profile for M303 cannot be authored in W03 without a prior registry restructure that adds numeric casilla IDs. This is a structural blocker. W03.P06.S19 is BLOCKED — see stop-and-report note in the W03.P06 records.

Corpus: 15 XLSX Diseño de Registros files (electronic record layouts, not form layout), plus 1 PDF from Orden EHA/3786/2008. None define the printed form box numbers — those appear in the official BOE form annex, not the Diseño de Registros.

### M180 — source gap: no numeric casilla IDs, no fixture PDF

The M180 registry casilla IDs are file-record position ranges (`"136-144"`, `"145-160"`, `"161-175"`). These are never printed literally on a declaración PDF. The `numeric_casilla` strategy cannot work. The existing `export_record` extraction profile correctly uses `named_label` targeting the summary labels (`Numero total de perceptores`, `Base retenciones…`, `Retenciones e ingresos a cuenta total`).

A `declaracion_pdf` profile for M180 would require `named_label` strategy against the printed form's label text — but no PDF fixture exists for M180 to validate the printed labels. The AEAT Diseño corpus contains only electronic record layout PDFs (file-structure documentation), not printed form samples.

**Verdict:** W03.P06.S20 is BLOCKED — no fixture PDF exists to ground the `declaracion_pdf` profile against the actual printed labels. Follow-up required: obtain a sample M180 declaración PDF justificante to determine printed label text, then author the profile in W04 alongside other `named_label` profiles.

### M190 — already resolved

The `2025-y-siguientes` revision of M190 already carries a `declaracion_pdf` extraction profile (`id = "modelo-190-declaracion-pdf"`) with real `named_label` targets for the three printed summary totals, authored during W02. W03.P07.S21 is already satisfied.

### M130 S22 cross-check — already satisfied

The M130 `2019-y-siguientes` revision already contains:
- Formula `modelo-130-rendimiento-neto` with `expression = subtract(01, 02)` targeting casilla `03`.
- `verification_expectations` with `id = "modelo-130-calculation-verification"` listing `computed_casillas = ["03", ...]`.
- The construct links both `formulas` and `verification_expectations`.

W03.P07.S22 is already satisfied — no change needed.

### M130/111/115/123 parse — passing

All 26 modelos validate (`test_committed_registry.py` 41/41 passing). Parser boundary tests 7/7 passing including M130, M111, M123 round-trips.

## Tests

- `test_committed_registry.py`: 41/41 passed — all 26 modelos valid
- `test_parser_boundary.py`: 7/7 passed — M130/M111/M123 parse unchanged
- `test_modelo_parity_coverage.py`: 1/1 passed
- No registry files modified in this step; tests confirm baseline health
