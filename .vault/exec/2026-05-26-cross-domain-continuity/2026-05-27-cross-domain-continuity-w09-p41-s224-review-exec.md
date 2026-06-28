---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S208]]"
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S252]]"
---

# cross-domain-continuity Code Review

## Commit under review

`79a14cba3` — #224 FU-#200: extend ModeloDetailRow union with M349 operador + M347 contraparte rows

## Status: REVISION REQUIRED

---

### CRASH-001 | CRITICAL | `_canonical_detail_rows` crashes on `Modelo349OperadorRow` — AttributeError at runtime

`src/aeat/domain/modelos/_calculation_revision.py` line 130 sorts rows by the key `(r.row_type, r.nif)`. `Modelo349OperadorRow` has no `nif` attribute; its identifier field is `nif_comunitario`. Any call that passes an `operador` row into `derive_calculation_revision_id` (or through `CalculationRevision.__init__`) will raise `AttributeError: 'Modelo349OperadorRow' object has no attribute 'nif'` before any hash is computed. This is a 100% reproducible crash on the happy path for M349 rows.

Fix: update the sort key to handle both shapes, e.g. `getattr(r, "nif", None) or getattr(r, "nif_comunitario", "")`.

---

### SCHEMA-002 | HIGH | `CalculationRevision.detail_rows` type annotation excludes new row types — Pydantic will reject them at construction

`src/aeat/domain/modelos/_calculation_revision.py` line 287 declares:

```python
detail_rows: tuple[Modelo184MemberRow | Modelo232VinculadaRow, ...] = Field(default_factory=tuple)
```

The union was not widened to include `Modelo349OperadorRow | Modelo347ContraparteRow`. With `strict=True` config on `CalculationRevision`, pydantic will raise a `ValidationError` whenever the CLI supplies `operador` or `contraparte` rows and passes them into `CalculationRevision`. The annotation must be updated to `tuple[ModeloDetailRow, ...]` (or the explicit four-type union) and the import updated accordingly.

---

## Critical question answers

**Q1 — Union extension (G5):** PASS. Both new types are added to `ModeloDetailRow` at `_row_models.py` line 350 without parallel implementations. No shims, no duplicate branches outside the single union.

**Q2 — M349 OperadorRow fields:** PASS. Fields match: `codigo_pais: _IsoCountryCode`, `nif_comunitario: _NifStr`, `razon_social: _NameStr` (optional), `clave_operacion: Literal["E","S","T","R","A","I","M"]`, `importe: Decimal`. Per-country NIF regex patterns cover DE (9d), FR (2alphanum+9d), IT (11d), IE (two alternates), NL (9d+B+2d), plus 10 additional countries and a generic fallback. Validation is advisory at parse time via `validate_m349_nif_format`.

**Q3 — M347 ContraparteRow fields:** PASS. Fields: `nif`, `nombre`, `importe_Q1/Q2/Q3/Q4` (all default 0), `clave_operacion: Literal["A"..."I"]` (default "A"), `pais_codigo: str | None`. Threshold `M347_THRESHOLD_EUR = Decimal("3005.06")` correctly grounds RD 1065/2007 art. 31.1. The `<=` comparison at `_validate_m347_threshold` correctly implements "supere" (strictly exceed).

**Q4 — CLI dispatch:** PASS. `_ROW_TYPES_SUPPORTED` extended to include `"operador"` and `"contraparte"`. `_parse_row_spec` dispatches cleanly in sequential `if/elif/else` within the existing single function. No parallel branch function added.

**Q5 — Engine wiring (casilla materialisation):** PARTIAL. Registry casillas for M347 contraparte fields are added to `0001-casillas.toml`. The M349 `op.*` casillas pre-existed in the registry. However, there is no evidence in this commit that `detail_rows` are materialised into positional casilla observations by a row-resolver for M349 or M347 — the `_canonical_detail_rows` function only handles the content-hash payload. The oracle tests requested in the brief (two operador rows → op-row.* casillas populated; two contraparte rows → contraparte block casillas populated) are absent. The tests added validate model construction and threshold enforcement only, not casilla materialisation.

**Q6 — M303 ↔ M349 cross-reference / INTRACOM_DISCREPANCY:** ABSENT. No cross-reference verification finding between M303 casilla 10/11 and M349 `clave_operacion=I` adquisiciones is implemented. This was a stated requirement in the review brief. No `INTRACOM_DISCREPANCY` finding surface exists in this commit.

**Q7 — Wizard parity (#228/#239):** No wizard catalogue entries added. Per brief, none required for work-unit-context rows. PASS.

**Q8 — Locale parity:** PASS. `es`, `en`, `ca`, `hu` all receive `row_m347_below_threshold` and `row_m349_invalid_nif` keys with substantive translations. `row_help` updated in all four locales to list `operador` and `contraparte` types. An unrelated `fail_observability_run_trace_persistence` key is also added in this commit across all four locales — not related to #224 scope but benign.

**Q9 — Oracle tests:** PARTIAL. Model construction and validation tests are present and well-grounded against legal authority. Anti-tautology tests exist for both row types. However the positional-casilla materialisation oracle tests are absent — no test proves that `operador` rows produce `op-row.*` casilla entries nor that `contraparte` rows produce `contraparte.*` casilla entries on a `CalculationRevision`.

**Q10 — Anti-tautology:** PASS. `TestModelo349OperadorRow.test_two_rows_distinguish_by_importe` and `TestModelo347ContraparteRow.test_two_rows_distinguish_by_quarterly_importe` both verify that modifying one row's field leaves the other row unchanged. `TestValidateM347Threshold.test_antitautology_threshold_check_reads_total_not_individual_quarters` verifies the sum path.

---

## Standing gate sweep

- **G1 (no naked env reads):** PASS. No `os.environ` / `os.getenv` introduced.
- **G2 (typed pydantic at boundaries):** FAIL — see SCHEMA-002. `CalculationRevision.detail_rows` annotation is stale and too narrow.
- **G3 (tr() for user messages):** PASS. Both new `BadParameter` raises in `_validate_m347_threshold` and `_parse_row_spec` use `tr()`.
- **G4 (no locale yml structure hand-edits):** Locale keys added structurally consistently. PASS.
- **G5 (no shims/re-exports/duplication):** PASS. Clean union extension, single `_parse_row_spec` function extended, no parallel API.
- **G6 (no tautological tests):** PASS. Tests are grounded against legal authority (Orden HAC/174/2020, RD 1065/2007) and anti-tautology proofs are present.

---

## Required fixes before merge

1. **CRASH-001 (CRITICAL):** Fix the `r.nif` sort key in `_canonical_detail_rows` to handle `Modelo349OperadorRow.nif_comunitario`. Add a test that constructs `derive_calculation_revision_id` with an `operador` row to lock the fix.

2. **SCHEMA-002 (HIGH):** Widen `CalculationRevision.detail_rows` annotation to `tuple[ModeloDetailRow, ...]` and update the import in `_calculation_revision.py`. Add a `CalculationRevision` construction test with `operador` and `contraparte` rows to prove pydantic accepts them.

## Follow-up items (not blocking merge once above are fixed)

- Q5/Q9: Casilla materialisation path for `operador` and `contraparte` rows into positional registry casillas is unimplemented. The rows are carried in the revision but never rendered into `casilla_values` or `observations`. This should be tracked as a follow-up step.
- Q6: M303 ↔ M349 `INTRACOM_DISCREPANCY` verification finding surface is not present. Track as follow-up.
