---
tags:
  - '#adr'
  - '#google-oauth'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-google-oauth-adr]]"
  - "[[2026-05-13-google-oauth-snapshot-adr]]"
  - "[[2026-05-13-google-oauth-taxonomy-adr]]"
  - "[[2026-05-12-google-oauth-adr]]"
  - "[[2026-05-06-google-oauth-research]]"
---

# `google-oauth` adr: `Calculation-to-Sheets visual verification surface` | (**status:** `accepted`)

## Problem Statement

The user-stated intent for the Google integration includes calculation-to-worksheet exports for human verification — visual surfaces a Spanish autónomo (or their accountant) can read to verify that the project's calculation truth registry produced the right casilla values for a given tax form. ADR-6 closes the design: worksheet layout, formula translation strategy, protected-range enforcement, provenance metadata, and Spanish UX for operators who don't read code.

**Amended 2026-05-14**: ADR-6 originally framed the calc-sheets surface as read-only by design, deferring two-way sync to ADR-7. The amendment supersedes that framing: ADR-8 (`2026-05-14-google-oauth-adr.md`) formalises a bidirectional pull contract specifically for the `Entradas` (Inputs) sheet, with `Cálculos / Resultado / Procedencia` remaining app-owned and protected. ADR-6 retains ownership of the four-sheet layout, the formula translation strategy, the provenance metadata schema, and the Spanish UX details. ADR-8 owns the schema-to-sheet engine module boundary, the tiered parity oracle stack, and the `aeat config google sync calc pull` bidirectional command. ADR-7's deferral verdict no longer governs the calc-sheets surface; it still governs ledger reverse-merge (transactions, invoices, rental) per its own scope.

## Considerations

- Research stream R4 surveyed Sheets API capabilities (formulas, named ranges, conditional formatting, data validation, protected ranges, comments) and industry exemplars (QuickBooks, Xero, Sheetgo, Coupler.io).
- The calculation truth registry (`src/aeat/domain/calculations/registry/`) is declarative TOML — declares casillas, formulas, inputs, source bindings, oracle references per modelo. ADR-6's export reads this registry plus the operator's actual filing inputs.
- ADR-2 reserved `/aeat-vault/_workspace/` for read-write workspace surfaces. ADR-6 writes Sheets exports there.
- ADR-7 will decide whether operator edits in these Sheets ever pull back to substrate. ADR-6 is read-only regardless of ADR-7's verdict.

## Constraints

- **Pydantic v2 strict** for the export-plan record and the per-sheet layout descriptor.
- **No partial implementations.** Every modelo currently in the registry can be exported; no "modelo 130 deferred" placeholders.
- **No backwards-compat.** No legacy Sheets layout reader; no migration from any prior export shape.
- **Partition by cell ownership.** Operator can edit the `Entradas` sheet (per §5); `Cálculos / Resultado / Procedencia / Guía / _Tariffs` are app-owned and protected. Operator edits to `Entradas` flow back to the local substrate via `aeat config google sync calc pull` (ADR-8). Foreign edits to app-owned sheets (operator explicitly unprotects + edits) are detected at pull time and refused with `CalcSheetForeignWriteError`.
- **Spanish UX.** AEAT-canonical terminology (casilla, base imponible, cuota, etc.); column labels in Spanish; "Guía de Lectura" reference sheet.

## Implementation

### 1. Spreadsheet structure — 4 sheets per modelo

Per exported modelo, the app creates one Spreadsheet under `/aeat-vault/_workspace/calc-modelo-<NNN>-<period>.gsheet` containing four sheets:

| Sheet | Purpose | Protection |
|---|---|---|
| **Entradas** (Inputs) | Operator-editable inputs (rendimiento, gastos, retenciones, etc.) | Unprotected |
| **Cálculos** (Calculations) | Casilla rows with formulas referencing Entradas | Protected (read-only to operator) |
| **Resultado** (Output) | Final liquidación (cuota a ingresar / devolver, deadline) | Protected |
| **Procedencia** (Provenance) | Per-casilla audit metadata: oracle source, legal ref, app version, last-generated timestamp | Protected |

A fifth sheet — **Guía de Lectura** — appears in every export, explaining the layout, colour coding, and what to do when the operator wants to verify or modify a calculation.

### 2. Export trigger

```
aeat config google sync calc export --profile <id> --modelo <NNN> --period <YYYYQn|YYYY|YYYY-MM> [--year <YYYY>] [--batch]
```

Creates (or updates if it exists) a Spreadsheet for the named modelo + period. File ID is persisted in `secure_objects_sync_state` with `provider_kind='google_drive'`, `namespace='calc-sheets'`, `object_key_hmac` derived from `(modelo, period, profile_id)`.

### 3. Formula translation strategy — hybrid

Mechanical translation where viable, static values + metadata where not:

| Registry formula shape | Sheets equivalent | Strategy |
|---|---|---|
| `a + b - c`, `a * rate`, `min(x, cap)` | `=Entradas!B2 + Entradas!B3 - Entradas!B4`, etc. | **Mechanical** |
| `if x > threshold else y` | `=IF(Entradas!B2 > 5000, Entradas!B2, B5)` | **Mechanical** |
| `sum(values)`, `avg(values)` | `=SUM(...)`, `=AVERAGE(...)` | **Mechanical** |
| Bracketed-rate lookup (e.g. IRPF progressive scale) | `=INDEX(_Tariffs!C:C, MATCH(B2, _Tariffs!A:A, 1))` + hidden `_Tariffs` sheet | **Mechanical via hidden lookup sheet** |
| Cross-modelo / cross-period dependencies | Static value + cell note explaining the source | **Static-with-metadata** |
| Domain-specific functions (e.g. autonomic-scale chain resolution) | Static value + cell note pointing to registry path | **Static-with-metadata** |

Static-with-metadata cells display the computed value (so operator sees the right number) and carry a cell note describing the underlying registry-side formula. Operator who wants to verify the formula reads the note and consults the registry source directly.

### 4. Per-casilla provenance metadata

Every row in the **Cálculos** sheet has corresponding columns in **Procedencia**:

| Cálculos column | Provenance metadata exposed |
|---|---|
| `Casilla` | (same — the casilla number) |
| `Descripción` | Per-casilla AEAT-canonical label |
| `Fórmula` | Sheets formula (mechanical) or static-value note |
| `Valor` | Computed value |

And in Procedencia (one row per casilla):

| Procedencia column | Source |
|---|---|
| `Casilla` | (same) |
| `Fuente / Oracle` | Registry's `oracle` field for that casilla (e.g. `trim-declaracion`, `manual-input`) |
| `Normativa` | Legal reference (e.g. `Art. 42 Ley 35/2006`) |
| `Última actualización` | Timestamp of the registry revision used + the app version that exported |
| `Versión registro` | Registry source SHA-256 prefix at export time |

Cell notes on Cálculos formula cells additionally embed Oracle + Normativa as hover-tooltips for at-a-glance verification without switching sheets.

### 5. Protected-range enforcement + bidirectional Entradas surface

`spreadsheets.batchUpdate` with `addProtectedRange` requests protects Cálculos, Resultado, Procedencia, Guía de Lectura, and the hidden `_Tariffs` lookup sheet. The protection is `warningOnly: false` and `requestingUserCanEdit: false` — operator cannot edit those sheets in Drive UI without explicitly unprotecting (which is an in-Drive operator action; the app does not block that capability at the Google ACL level because the operator owns the file). Foreign writes to app-owned cells are detected at `sync calc pull` time via Drive `headRevisionId` change + cell-address comparison; the pull refuses with `CalcSheetForeignWriteError` listing the cells the operator edited outside `Entradas`.

The `Entradas` sheet is left unprotected and is the canonical operator-edit surface. Operator can change input values and watch the Cálculos formulas recompute live in Sheets. To flow those edits back into the local substrate (and trigger a fresh `CalculationRevision`), operator runs `aeat config google sync calc pull --modelo <NNN> --period <p>` per ADR-8. Operator may then re-run `aeat config google sync calc export --period <p>` to re-write the Sheet from the new authoritative state (idempotent under the existing semantics); the round-trip is multi-turn.

### 6. Spanish UX details

- All sheet names, column headers, cell labels in Spanish.
- AEAT-canonical terminology: `casilla`, `base imponible`, `cuota a ingresar`, `cuota a devolver`, `rendimiento`, `gastos deducibles`, etc.
- Colour coding via conditional formatting:
  - **Blue** — input cells (Entradas sheet)
  - **Green** — calculated cells (Cálculos values)
  - **Red** — alert cells (e.g. `Cuota a devolver` is negative → operator owes)
  - **Yellow** — warning cells (e.g. unusual value relative to historical periods)
- Guía de Lectura sheet content (header):
  - Cómo leer este libro
  - Qué hojas son editables y cuáles no
  - Cómo verificar un cálculo (paso a paso)
  - Qué hacer si un valor no es correcto

### 7. CLI surface

```
aeat config google sync calc export --profile <id> --modelo <NNN> --period <period> [--batch]
aeat config google sync calc pull   --profile <id> --modelo <NNN> --period <period> [--force --resolve {local,remote}]
aeat config google sync calc list   --profile <id> [--format json|text]                            # lists exported Sheets per profile
aeat config google sync calc delete --profile <id> --modelo <NNN> --period <period>    # removes the workspace Sheet
```

`calc export` is idempotent: re-running on the same (modelo, period) updates the existing Sheet in place rather than creating a new file. `calc pull` reads the operator's `Entradas` edits and applies them to the local substrate per ADR-8; refer there for the full bidirectional contract.

### 8. Out of scope (deferred)

- Two-way sync from app-owned Cálculos / Resultado / Procedencia cells (operator unprotects and overwrites). ADR-8 detects + refuses this with `CalcSheetForeignWriteError`. A future amendment to ADR-8 could add a `--accept-foreign-cell-overrides` opt-in but v1 refuses.
- Multi-modelo single-Spreadsheet (one Sheet per modelo in one Spreadsheet). v1 creates one Spreadsheet per (modelo, period).
- Comparative views across periods (Q1 vs Q2 column-side-by-side). v1 = one period per Sheet.
- Docs API exports for prose-shaped tax reports. No consumer; out of scope (consistent with audit's refutation of Docs round-trip).

## Rationale

**4-sheet layout over single-sheet or multi-workbook.** Single-sheet would mix inputs, calculations, output, and provenance — hostile to operator scan-reading. Multi-workbook (one Spreadsheet per casilla) is over-fragmented. Four sheets per modelo balances cognitive load: operator opens one file per filing, finds inputs to edit on one sheet, sees results on another, audits provenance on a third, reads instructions on a fourth.

**Hybrid formula translation over fully-mechanical or fully-static.** Fully-mechanical doesn't generalise to domain functions (autonomic-scale chains, cross-modelo dependencies). Fully-static loses the "live recompute when I change inputs" verification UX that's the whole point. Hybrid — mechanical for simple arithmetic and conditionals, static-with-metadata for complex paths — captures the right balance.

**Protected ranges over no-protection or document-level locking.** No-protection lets operators corrupt formulas accidentally. Document-level locking (read-only sharing) breaks the input-editing UX. Per-range protection allows Entradas to stay editable while everything downstream is read-only.

**Provenance as a dedicated sheet + cell notes over notes-only.** Cell notes give hover-tooltips for at-a-glance verification; the dedicated sheet gives a sortable, filterable, exportable audit ledger. Operator who wants to drill into one casilla hovers; operator who wants to audit a whole filing reads the sheet.

**Spanish UX over English-with-translations.** Operator is a Spanish autónomo; accountant is Spanish-speaking. AEAT-canonical terms are Spanish. English column labels would force mental translation on every operation.

## Consequences

**Positive.**

- Operator can visually verify any modelo's calculation chain without leaving Drive UI.
- Inputs sheet editing gives "what-if" recomputation in real time — useful for tax planning.
- Provenance sheet is auditable independently; sortable by oracle source or legal reference.
- Cell notes carry just-in-time context without polluting the column structure.

**Negative.**

- Multi-sheet structure is more complex than a flat dump. Operators unfamiliar with Sheets navigation may need orientation. Mitigated by the Guía de Lectura sheet.
- Static-with-metadata cells lose the live-recompute property — operator-changing Entradas doesn't update them. Cell note explains why; this is the cost of registry formulas that don't translate to Sheets natively.
- Spanish-only UX excludes English-speaking accountants. Acceptable trade-off given the autónomo target audience.

**Neutral.**

- Spreadsheet quota cost is bounded: one file per (modelo, period); ~10 modelos × 4 quarters = 40 files lifetime per operator-year. Well within free-tier Sheets storage.
- A future amendment may add a "compare two periods" sheet or multi-modelo composite views without breaking ADR-6's per-modelo baseline.

## References

External:
- Sheets API `batchUpdate` reference — `https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate`
- Protected Ranges — `https://developers.google.com/workspace/sheets/api/samples/ranges`
- Conditional formatting — `https://developers.google.com/workspace/sheets/api/samples/conditional-formatting`
- Industry exemplars (QuickBooks Audit Trail, Xero report export) — drawn from R4 research.

Internal:
- `[[2026-05-13-google-oauth-adr]]` — bucket layout (workspace bucket reserved by ADR-2).
- `[[2026-05-13-google-oauth-snapshot-adr]]` — encryption boundary (visualisation Sheets are workspace, not mirror; different encryption profile).
- `[[2026-05-13-google-oauth-taxonomy-adr]]` — per-domain export taxonomy.
- `[[2026-05-12-google-oauth-adr]]` — provider abstraction.
- `[[2026-05-06-google-oauth-research]]` — R4 Sheets visualisation grounding.
