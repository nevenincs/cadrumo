---
tags:
  - "#plan"
  - "#declaracion-extractor"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-declaracion-extractor-adr]]"
  - "[[2026-04-21-declaracion-extractor-research]]"
---

# `declaracion-extractor` plan

## Phase 1 — module skeleton + shared primitives

### Step 1.1 — Create `src/aeat/adapters/inbound/declaracion/` package

- `__init__.py` exporting `parse_declaracion`, `DeclaracionFiling`, `DeclaracionParseError`, `TemplateRevision`, `ExtractionWarning`.
- `_schema.py` with the pydantic records per ADR §3.
- `_errors.py` with `DeclaracionParseError < PdfFilingImportError`.
- `_extract.py` with primitives `read_acroform`, `apply_label_regex`, `apply_bbox_extraction` — pure functions, no state.
- `_extractor.py` with the `DeclaracionExtractor` ABC.
- `_detect.py` with `detect_template_revision`.
- `_extractors/__init__.py` with the empty registry + registration decorator.
- `_parsers/_pdfplumber_backend.py`, `_parsers/_pypdf_backend.py`.
- `test_extractor.py` (phase 2 populates).

### Step 1.2 — Promote shared helpers

Move `_parse_decimal`, `_strip_accents`, `_require` from `src/aeat/domain/justificante/_extract.py` into `src/aeat/adapters/inbound/pdf/_shared.py`. Retain backwards-compatible re-imports in the justificante module.

### Step 1.3 — Unit tests for primitives

- `test_parse_decimal` round-trip: `"1.234,56"` → `Decimal("1234.56")`, `"1234.56"`, `"1,234"` (treated as decimal with `,`), edge: empty, `"-"`, negative.
- `test_strip_accents` idempotent + NFKD-based.
- `test_apply_label_regex` — synthetic text with "01 Ingresos 1.234,56", regex returns `{"01": Decimal("1234.56")}`.

## Phase 2 — Modelo 130 v2025 extractor

### Step 2.1 — L3 generator for Modelo 130

`tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_130_generator.py`:

- `Modelo130GenParams` pydantic: `año`, `template_revision`, `tax_id`, `casilla_values: Mapping[str, Decimal]` covering all 19 casillas.
- `generate(params) -> tuple[bytes, GroundTruth]` renders via reportlab + `_generator_shared`.
- Layout mirrors AEAT's Modelo 130 PDF: header ("Modelo 130 Pago fraccionado IRPF Ejercicio YYYY Período"), NIF block, casillas 01–19 with labels and numeric boxes, footer (CSV + date).

### Step 2.2 — Extractor `_extractors/modelo_130_v2025.py`

- Subclass of `DeclaracionExtractor` with `template_revision = TemplateRevision(modelo="130", año=2025, revision="2025.01")`.
- `label_regex_map`: 19 entries (`"01": _re("01\\s+Ingresos íntegros.*?([\\d\\.,]+)")`, …).
- `bbox_map`: 19 entries (learned from the L3 generator + any L1/L2 anchors).
- Registers itself in `_extractors/__init__.py`.

### Step 2.3 — Tests

- `test_modelo_130_v2025_extract_synthetic` — parametrised over 500 `Modelo130GenParams` permutations. For each: generate PDF → `parse_declaracion(path)` → assert `result.values` matches `params.casilla_values`. Markers: `@pytest.mark.unit`, `@pytest.mark.domain_financial_input`, `@pytest.mark.fixture_tier_l3`.
- `test_modelo_130_v2025_fidelity_anchors` — parametrised over available L1/L2 anchors for `(130, 2025, 2025.01)`. `xfail(strict=True)` until anchors land.
- `test_modelo_130_v2025_partial_extraction` — generate PDF with 3 casillas' values blanked; assert `extraction_status == "partial"`, warnings list the 3 missing casillas.

### Step 2.4 — CLI wiring

- Extend `aeat filing import` with `--from-declaracion PATH --modelo 130 --año 2025` path.
- Smoke test in `src/aeat/entrypoints/cli/filing/test_filing_cli.py`.

### Step 2.5 — Audit pass

- Subagent runs: walk `src/aeat/adapters/inbound/declaracion/` + its tests, report any TODO / hardcoded path / missing marker / bare dict / non-relative import. Findings → audit doc under `.vault/audit/2026-04-21-declaracion-extractor-phase-2-audit.md`. Any hard findings block phase 3.

## Phase 3 — Modelo 303 v2024-Sept extractor

Mirrors phase 2 with ~88 casillas and the post-HAC/819/2024 renumbering.

### Step 3.1 — L3 generator (modelo 303 v2024_2)

### Step 3.2 — Extractor `_extractors/modelo_303_v2024_2.py`

### Step 3.3 — Tests + audit

## Phase 4 — Modelo 303 v2025 extractor

### Step 4.1 — L3 generator reuse (small delta from v2024_2)

### Step 4.2 — Extractor `_extractors/modelo_303_v2025.py`

### Step 4.3 — Tests + audit

## Phase 5 — CI + coverage-matrix updates

Per concrete extractor landing, update `docs/coverage/modelos.md` L3 / L1 / L2 anchor columns + the `aeat.adapters.inbound.declaracion` column.

## Phase 6 — Loop audit

After phases 2, 3, 4 each: run `vaultspec-code-review` subagent with scope = the phase's diff. Resulting audit doc lives under `.vault/audit/`. Any severity-high finding blocks the next phase.

## Exit criteria (per phase)

- All tests green under `uv run pytest -m unit src/aeat/adapters/inbound/declaracion/`.
- `uv run ruff check src/aeat/adapters/inbound/declaracion/` clean.
- `uv run ty check src/aeat/adapters/inbound/declaracion/` clean.
- Code-review audit doc has zero open severity-high findings.
- Kent UX roleplay recorded in the phase's exec summary.

## Kent UX roleplay per phase

**Phase 2 (after Modelo 130 v2025 lands)**:

- Kent exports his 2025Q1 Modelo 130 declaración PDF from Sede.
- Runs `aeat filing import --from-declaracion ~/Downloads/declaracion-130-2025Q1.pdf`.
- Sees: "Parsed Modelo 130 2025Q1 declaración (template 2025.01). 19 of 19 casillas extracted. Draft 75a6bb365c8d0ee7 saved to …".
- Runs `aeat filing show 75a6bb...` — sees every casilla populated, `status=READY_TO_SUBMIT` because all values came in as literals.
- Runs cluster-E's `aeat filing verify 75a6bb...` — sees "Verified: every computed casilla re-derived to within 0.01 €".

**Phase 3 (after Modelo 303 v2024_2 lands)**:

- Kent has a 2024Q3 Modelo 303 (post-Sept renumbering).
- Runs `aeat filing import --from-declaracion ~/…` — extractor auto-detects template `303.2024.09`.
- Gets a complete 88-casilla draft + calc-verification verdict.

## Non-goals

- Modelo 100, 390 — other clusters / blocked.
- OCR scans — future.
- No changes to `FilingDraft` schema. `DeclaracionFiling` is a distinct record; it feeds `build_draft` via an input dict.
