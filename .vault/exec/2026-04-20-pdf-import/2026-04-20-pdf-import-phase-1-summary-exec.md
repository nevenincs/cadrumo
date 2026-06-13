---
tags:
  - "#exec"
  - "#pdf-import"
date: "2026-04-20"
modified: '2026-04-20'
related:
  - "[[2026-04-20-pdf-import-plan]]"
  - "[[2026-04-20-pdf-import-adr]]"
  - "[[2026-04-20-pdf-import-research]]"
---

# pdf-import phase-1 summary

## Delivered

- `aeat filing import --from-justificante <path>` lands end-to-end: parses the PDF via existing `aeat.domain.justificante.parse_justificante`, reconstructs a `FilingDraft` scaffold via the registered builder with empty inputs, and co-persists a `SubmittedFiling` record (status `SUBMITTED`, `justificante_csv`, `justificante_pdf_path`, `submitted_at` in UTC) so the import can serve as the baseline for amendment flows (`#93`, `#234`, `#235`).
- Period canonicalisation (`1T`+`2026` → `2026Q1`, `12`+`2024` → `2024-12`, `0A`+`2025` → `2025A`) covers quarterly, monthly, and annual modelos.
- Advisory warnings surfaced trilingually (es/en/hu) tell Kent the line-level casilla values are not carried by the PDF and must be filled via `aeat filing build` or manual editing.
- Live smoke run against `tests/fixtures/justificantes/modelo_130_2026Q1.pdf` produces a persisted draft + submission + `aeat filing list` row.

## Files changed

- `src/aeat/domain/justificante/_schema.py`, `src/aeat/domain/justificante/_extract.py` — expose `ejercicio` on `Justificante`.
- `src/aeat/domain/justificante/test_parser.py` — assertions for the new `ejercicio` field across the three fixture PDFs.
- `src/aeat/application/filing/_errors.py` — add `FilingImportError`.
- `src/aeat/application/filing/_import.py` — new module: `import_filing_from_justificante`, `JustificanteImportResult`, `_normalise_period`, `_build_submission_record`, `_EMPTY_CASILLA_WARNING`.
- `src/aeat/application/filing/__init__.py` — re-export the import API.
- `src/aeat/application/filing/test_import.py` — unit coverage for the import path, period canonicaliser, unsupported-modelo error, missing-PDF error.
- `src/aeat/entrypoints/cli/filing/__init__.py` — new `import` Typer subcommand mapped onto the import helper.
- `src/aeat/entrypoints/cli/filing/test_filing_cli.py` — CLI smoke tests for the import command (happy path, missing PDF, unsupported modelo).
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py` — **pre-existing bug unblocker**: re-export `AuthProviderDescription` from `._protocols` so `aeat.adapters.outbound.aeat.export` can import it (no functional change; restores the `aeat.application.filing → aeat.adapters.outbound.aeat.export` import chain main was already broken on).

## Live-write safety

Zero coupling introduced. No new `SubmissionEngine` callers, no new `live_transport_supported=True` construction sites, no new live-submission CLI commands. The import command registers under `aeat filing`; the companion submission record is written directly via pydantic JSON dump (no engine invocation).

## Quality gates

- `uv run ruff check src/aeat/` — clean.
- `uv run ty check src/aeat/…` on every touched module — clean.
- `uv run pytest src/aeat/application/filing/ src/aeat/domain/justificante/ src/aeat/entrypoints/cli/filing/ -m unit` — 88 passed.
- `uv run pytest src/aeat/adapters/outbound/aeat/export/ -m unit` — 44 passed (no regressions).
- Manual smoke: `AEAT_DRAFTS_DIR=... AEAT_SUBMISSIONS_DIR=... uv run aeat filing import --from-justificante tests/fixtures/justificantes/modelo_130_2026Q1.pdf` succeeds, emits the warning, and `aeat filing list` shows the reconstructed `130 / 2026Q1` draft.

## Acceptance criteria (from `#271`)

- [x] Kent runs the command on a real justificante PDF and `aeat filing list` shows the reconstructed draft.
- [x] Draft carries correct `modelo` (`130`) + `period` (`2026Q1`) + `presented_at` (via companion `SubmittedFiling.submitted_at`, UTC-normalised) + `csv` (via companion `SubmittedFiling.justificante_csv`).
- [x] No cert auth is required at any point — the code path never touches `aeat.adapters.outbound.aeat.auth` or the submission engine's transport.
