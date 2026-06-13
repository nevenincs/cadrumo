---
tags:
  - '#research'
  - '#modelo-export-evidence-parity'
date: '2026-06-03'
modified: '2026-06-03'
related: []
---



# `modelo-export-evidence-parity` research: `ledger-evidence-bundled modelo exports + official workbook parity`

Current-state and gap analysis for the operator directive: implement the
complete `ledger -> calculation engine -> modelo calculation -> modelo export`
backend, where every ledger-derived modelo revision is pegged to the ledger
snapshot it was computed from, the export bundles its own evidence (ledger +
manual entries + fact basis), and the exported xls / Google-Sheets workbook is
in 100% parity with the official AEAT casilla calculations and published
workbook structure — offline and online.

## Findings

### A. The modelo->workbook export already mirrors official registry structure

The calc-sheets export plan is the existing, registry-grounded modelo workbook
surface (not the flat ledger dump). `build_export_plan(snapshot, inputs?,
relations?)` in `application/storage/calc_sheets/_engine.py` walks the
`ModeloRevision`'s casillas / formulas / bindings / parameters and emits a
strict `SheetExportPlan`:

- `value_cells` (labels, operator-input prefills, parameter values),
- `formula_cells` (computed casillas as **live A1 spreadsheet formulas**, with a
  `rounding_rule` of money/integer/none),
- `tariffs` (parameter scalars + bracket tables),
- `provenance` (per-computed-casilla audit rows),
- `protected_ranges` (Cálculos / Procedencia / Tarifas / Guía are read-only),
- `cell_constraints` (sign/min/max + legal-ref notes),
- `row_sets` (repeating Detalle blocks),
- `guide` (workbook intro),
- `metadata` (`SheetExportMetadata`: modelo_id, revision_id, filing_year,
  period, engine_version, `registry_sha`, exported_at).

Casilla ordering and section grouping derive from the registry
`CasillaDefinition` (`id`, `number`, `segmento?`, `label`, `section`,
`data_type`, `input_kind`, `formula?`, `binding?`, `legal_refs`, `source_refs`)
in `domain/calculations/registry/_schema.py`. The official-completeness contract
is the `CalculationCompletenessManifest` (derived from the AEAT Diseño de
Registros), validated `manifest-required ⊆ declared`.

The Google apply adapter (`adapters/outbound/google/_calc_sheets_apply.py`)
materialises the plan into a real Sheet: it writes live formulas verbatim (the
Sheets engine evaluates them), expands the grid, sets protected ranges, writes
data-validation constraints + legal-ref cell notes, and stamps developer
metadata (`aeat_registry_sha` etc.). The pull adapter validates that metadata
before merging operator edits back.

**Parity gaps observed:** the apply adapter writes **no cell formatting** (no
number formats, no section-header styling, no start/final visual anchors); the
"start (inputs) -> final (resultado)" boundary is implicit in tab/section
ordering, not explicitly labelled; and there is no automated gate asserting the
exported grid is structurally faithful to the official AEAT workbook layout for
each modelo.

### B. CRITICAL: the ledger fact-basis is never bundled — only fingerprinted

`domain/modelos/_ledger_filing_snapshot.py` `LedgerFilingSnapshot` stores **only
content fingerprints**: `rows: tuple[LedgerRowFingerprint, ...]` where each row
is `(transaction_id, sha256)`, plus an aggregate `snapshot_fingerprint` and
`captured_at`. It is captured at verify time by
`compute_ledger_filing_snapshot` and pegged onto
`CalculationRevision.ledger_filing_snapshot`.

This is sufficient for **staleness detection** (the hash diff surfaces drift)
but it is **not evidence**: the actual contributing transaction data, the manual
casilla inputs, and the FX/derivation fact basis cannot be reconstituted from a
revision. Therefore:

- a modelo revision cannot answer "show me the exact ledger rows and manual
  entries that produced casilla X = N";
- the modelo export (calc-sheets or flat) carries **no ledger evidence** — there
  is no bundled fact basis and no resolvable reference to where it lives;
- in a legally-sound filing system the evidence basis is part of the filing
  artefact; today it is absent.

`source_transaction_ids` on the revision is a list of ids (pointers), but the
rows they point to are mutable/blockable and not snapshotted as data.

### C. The flat exports are not modelo-structure mirrors

`application/export/_tabular.py` (`serialize_tabular_rows` -> csv/jsonl/xlsx) and
the W15 ledger workbook export are **flat row dumps** of transactions, unrelated
to modelo casilla structure or formulas. They are an operator backup surface,
not a filing artefact.

### D. Hexagonal placement the rollout must respect

- Pure records + fingerprint diff: `domain/modelos/_ledger_filing_snapshot.py`
  (no ledger-read dependency).
- Transaction-aware capture: `application/aggregation/_ledger_filing_snapshot.py`.
- Calc-sheets plan build: `application/storage/calc_sheets/`.
- Google network adapters: `adapters/outbound/google/` (Sheets) +
  `adapters/outbound/storage/_google_drive.py` (Drive).
- Registry authority: `domain/calculations/registry/` + `_data/registry/`.

### E. Decisions this research feeds

1. A foundational ADR: ledger-derived revisions must bundle the **typed ledger
   snapshot DATA + manual entries + fact basis** (not just fingerprints), pegged
   to the revision, and exports must carry that evidence (bundled, or a
   resolvable in-system reference) — reusing the existing `LedgerFilingSnapshot`
   shape, `Transaction` model, `CalculationRevision`, and core enums/errors.
2. An export-parity ADR: uniform workbook UX — explicit labelled start/final,
   official-casilla-structure mirror enforced by a parity gate, live calculation
   engine present, offline (xls) and online (Sheets) sharing one plan builder.
3. An L4 Epic plan rolling both out across all supported ledger-fed modelos.
