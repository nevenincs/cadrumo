---
tags:
  - "#plan"
  - "#pdf-import"
date: "2026-04-20"
modified: '2026-04-20'
related:
  - "[[2026-04-20-pdf-import-adr]]"
  - "[[2026-04-20-pdf-import-research]]"
---

# `pdf-import` plan: `reconstruct-filing-draft-from-justificante-pdf`

## Goal

Ship the `aeat filing import --from-justificante <path>` CLI command end-to-end so Kent can reconstruct a past filing from a downloaded justificante PDF with zero AEAT auth. Closes issue `#271`.

## Step 1 — Expose `ejercicio` on `Justificante`

**Files**: `src/aeat/domain/justificante/_schema.py`, `src/aeat/domain/justificante/_extract.py`.

- Add `ejercicio: str | None = Field(default=None, max_length=8)` to `Justificante`.
- In `extract_justificante`, resolve `_EJERCICIO_RE.search(normalised)` once (already computed), surface the stripped match to the `Justificante(...)` call. Remain `None` if the regex misses (forward-compatible with historical PDFs that only print the period).
- **No** test changes needed for `justificante/test_parser.py` beyond adding an assertion for the new field's expected value on the three committed fixtures (`"2026"`, `"2026"`, `"2025"`).

## Step 2 — Add `aeat.application.filing._import`

**New file**: `src/aeat/application/filing/_import.py`.

Public surface (re-exported from `aeat.application.filing.__init__`):

- `class JustificanteImportResult(BaseModel)` — strict, frozen; fields `draft: FilingDraft`, `submission: SubmittedFiling`, `warnings: tuple[Translatable, ...]`.
- `def import_filing_from_justificante(pdf_path: Path, *, schema_provider: CasillaSchemaProvider) -> JustificanteImportResult`.

Behaviour:

1. `justificante = parse_justificante(pdf_path)`.
2. `period = _normalise_period(modelo=justificante.modelo, ejercicio=justificante.ejercicio, raw_period=justificante.period)`.
    - If `ejercicio` is `None` and the raw period is not already canonical, raise `FilingImportError` — a new exception under `aeat.application.filing._errors` rooted at `FilingDraftError`.
    - Quarterly: `_QUARTER_RE = re.compile(r"^([1-4])T$")` → `f"{ejercicio}Q{n}"`.
    - Monthly: `_MONTH_RE = re.compile(r"^(0[1-9]|1[0-2])$")` → `f"{ejercicio}-{m}"`.
    - Annual (`"0A"`): → `f"{ejercicio}A"` (matches existing Modelo 100/390 annual convention).
    - Already-canonical input passes through unchanged (safety net).
3. `profile = FilingOperatorProfile(tax_id=justificante.tax_id, display_name=f"Imported filing {justificante.csv}", applicable_modelos=(justificante.modelo,))`.
4. `draft = build_draft(modelo=justificante.modelo, period=period, profile=profile, inputs={}, schema_provider=schema_provider)`.
    - Wrap `FilingBuilderError` with a friendlier message naming the registered modelos, re-raise as `FilingImportError`.
5. `submitted_at = justificante.presented_at.replace(tzinfo=ZoneInfo("Europe/Madrid")).astimezone(UTC)`.
6. Construct `SubmissionAttempt` (single) and `SubmittedFiling` per the ADR. `submission_id = hashlib.sha256(f"{justificante.csv}:{draft.draft_id}".encode()).hexdigest()[:16]`.
7. Assemble warnings (`tuple[Translatable, ...]`): trilingual payload describing that line-level casilla values were not extracted.
8. Return `JustificanteImportResult(draft=..., submission=..., warnings=...)`.

**Error hygiene**: All raises inherit `FilingDraftError` → `AeatError`.

## Step 3 — Extend `aeat.application.filing._errors`

Add `FilingImportError(FilingDraftError)` — single-line class with docstring. Re-export from `aeat.application.filing.__init__`.

## Step 4 — Re-export from `aeat.application.filing`

**File**: `src/aeat/application/filing/__init__.py`.

- Import `import_filing_from_justificante`, `JustificanteImportResult`, `FilingImportError` from `._import` and `._errors`.
- Append to `__all__`.

## Step 5 — Wire the CLI

**File**: `src/aeat/entrypoints/cli/filing/__init__.py`.

- Add `_import_filing` command under the `@app.command("import")` decorator.
- Flags: `--from-justificante` (required `Path`). Future flags like `--from-aeat` are out of scope.
- Resolve settings; look up `settings.aeat_submissions_dir` for the submission persistence.
- Call `import_filing_from_justificante(...)`.
- Persist the draft via existing `_save_draft(result.draft)`.
- Persist the submission manually (submission_engine not needed — this is an offline reconstruction). Write to `settings.aeat_submissions_dir / f"{submission.submission_id}.json"` using `submission.model_dump_json(indent=2)`.
- Print each warning (English render via `Translatable.get("en")`) as `typer.echo(...)` with a leading `[warning]` prefix.
- `_render_draft(result.draft)` so Kent sees the scaffold immediately.
- Error mapping: `FilingImportError`, `FilingDraftError`, `JustificanteParseError`, `JustificanteCsvNotFoundError` → `typer.BadParameter`.

## Step 6 — Unit tests

**New file**: `src/aeat/application/filing/test_import.py`.

- Module markers: `pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]`.
- Fixtures: reuse `tests/fixtures/justificantes/modelo_130_2026Q1.pdf` and `...303_2026Q1.pdf`.
- Tests:
    - `test_import_modelo_130_fixture` — asserts modelo, period canonicalised to `2026Q1`, `profile_tax_id == "00000000T"`, every value's `kind is FilingValueKind.EMPTY`, `draft.status` is a valid enum member.
    - `test_import_modelo_303_fixture` — analogous coverage, plus asserts `submission.justificante_csv == "ZZZZ9999YYYY8888"` and `submitted_at.tzinfo == UTC`.
    - `test_import_unsupported_modelo` — uses `modelo_100_2025A.pdf`, asserts `FilingImportError` with a message that names the registered modelos.
    - `test_import_missing_pdf` — tmp path that doesn't exist, asserts `JustificanteParseError`.
    - `test_normalise_period` — parametrised unit covering `("1T", "2026")→"2026Q1"`, `("12", "2026")→"2026-12"`, `("0A", "2025")→"2025A"`, `("2026Q1", None)→"2026Q1"` passthrough, and a malformed `("XX", "2026")` → `FilingImportError`.
    - `test_warning_mentions_line_level` — checks the warning's `"en"` translation contains "casilla" or "line-level".

**Amended file**: `src/aeat/entrypoints/cli/filing/test_filing_cli.py`.

- Add `TestFilingImportCLI` class with:
    - `test_import_writes_draft_and_submission` — points `AEAT_DRAFTS_DIR` + `AEAT_SUBMISSIONS_DIR` at tmp dirs, runs `aeat filing import --from-justificante <fixture>`, asserts both JSON artefacts exist, output contains the warning marker.
    - `test_import_rejects_missing_pdf` — exit code != 0, no drafts written.

**Amended file**: `src/aeat/domain/justificante/test_parser.py`.

- Extend the three `TestParseJustificante` assertions to include `record.ejercicio == "2026"` / `"2025"`.

## Step 7 — Lint & type checks

- `uv run ruff check src/aeat`
- `uv run mypy src/aeat/application/filing/_import.py src/aeat/entrypoints/cli/filing/__init__.py src/aeat/domain/justificante/_schema.py src/aeat/domain/justificante/_extract.py`
- `uv run pytest -x -q src/aeat/application/filing/test_import.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/domain/justificante/test_parser.py`

## Step 8 — Vaultspec + PR

- Create exec folder `.vault/exec/2026-04-20-pdf-import/` with per-step records + summary as work lands.
- Ensure `.vault/audit/` has no overlap (none — this is a new feature).
- Open PR linking `#271`, reference the ADR / plan / research wiki-links, attach the pipeline-review checklist.
