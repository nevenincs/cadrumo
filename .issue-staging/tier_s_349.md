**Kent success moment:** Kent has the declaración PDF of his Modelo 349 filing for any supported ejercicio (2024/2025/2026). He runs `aeat filing import --from-declaracion <pdf>`. The tool extracts every per-counterparty record line, sums them, and confirms the per-counterparty totals equal the printed resumen totals to within 0.01 €.

## Tier — S (Summary / Informative return)

This is an **information return**, not a liquidation. There is no formula ruleset because there are no computed casillas derived from other casillas. Pass criteria: per-counterparty schema + resumen-totals parity.

## Scope

Modelo 349 — declaración recapitulativa de operaciones intracomunitarias (mensual / trimestral). Per-operador record lines with ClaveOperacion enum + resumen totals.

## Current state (2026-04-22 audit)

Declaración extractor MVP (4 summary casillas only). No ruleset. No integration test. Crítico para integración con Modelo 303 (IVA intracomunitario).

## Definition of Done — pass criteria

### Per-counterparty record schema

- [ ] Pydantic v2 frozen model `Modelo349RecordLine` with all BOE-required fields (enumerate every field in PR body with BOE citation)
- [ ] Strict typing (Decimal for monetary, date for fechas, Enum for closed catalogues — e.g. `ClaveOperacion` for 349)
- [ ] `frozen=True, strict=True, extra="forbid"` per project mandate

### Extractor

- [ ] Declaración extractor captures **every** per-counterparty record line on the PDF, not just the resumen block (current MVP captures summary totals only)
- [ ] Resumen-totals casillas captured alongside per-record data
- [ ] Round-trip: `generator(records) → PDF → extractor == records` (identity)

### Totals parity

- [ ] Sum of per-counterparty record amounts equals printed resumen casilla(s) within 0.01 €
- [ ] Parity test in `src/aeat/verification/_verify.py` (or a new `_verify_summary.py` if the existing API is ruleset-bound) that asserts the parity and emits a `VERIFIED` verdict on success, `NEEDS_REVIEW` on mismatch
- [ ] Discrepancy classifier handles the summary case (extraction-bug vs PDF-arithmetic-mismatch)

### Per-year completeness

- [ ] Extractor + generator tested against 2024, 2025, 2026 templates
- [ ] `.vault/reference/2026-349-rule-delta.md` manifest listing any schema changes per year with BOE citations (e.g., 347 umbral 3005,06 €, ClaveOperacion additions)

### PDF fixtures

- [ ] L1 public-anchor real PDF hash-pinned in `tests/fixtures/pdf_corpus/l1_public_anchors/modelo_349/` **OR** explicit `.vault/reference/` waiver
- [ ] Synthetic L3 generator via `QuarterlyGenParams` scaffold extended with per-record-line support (or bespoke if needed)
- [ ] Integration test in `tests/integration/test_kent_workflows.py` asserting CLI path `VERIFIED` on happy path + `NEEDS_REVIEW` on tampered totals

### Test discipline

- [ ] `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`
- [ ] No mocks / fakes / stubs / skips
- [ ] Tests colocated Rust-style

### Closure evidence

- [ ] `.vault/exec/YYYY-MM-DD-modelo-349-summary-verify/…-summary.md`
- [ ] `docs/coverage/modelos.md` row flipped in applicable columns
- [ ] PR body cites BOE / Orden HAC article numbers for every required field

---

**Parent EPIC:** #316
