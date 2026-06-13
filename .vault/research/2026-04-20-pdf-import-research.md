---
tags:
  - "#research"
  - "#pdf-import"
date: "2026-04-20"
modified: '2026-04-20'
related:
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
---

# pdf-import research: cert-free import of a past filing from a justificante pdf

## Goal

GitHub issue `#271` asks for `aeat filing import --from-justificante <path>`: parse a justificante PDF Kent already downloaded from the AEAT portal and reconstruct a local `FilingDraft` scaffold so subsequent amendment, review, and verification flows can treat that past filing as first-class project state — **without** any AEAT certificate auth.

The task is orthogonal to the cert-blocked `fetch_filing_detail` path (`#222`) and the broader EPIC `#233` (aeat revise — import past filings).

## Existing building blocks

- `src/aeat/domain/justificante/_extract.py` already converts the raw PDF text into a frozen `Justificante` record (`csv`, `modelo`, `period`, `presentation_id`, `presented_at`, `tax_id`, `total_a_ingresar`, `total_a_devolver`, `verification_url`, `source_pdf_path`, `source_pdf_sha256`, `parsed_at`).
    - Public surface: `from aeat.domain.justificante import parse_justificante` (public in `__init__.py`).
    - `_EJERCICIO_RE` is used internally but the parsed ejercicio string is NOT surfaced on the `Justificante` schema.
    - `presented_at` is returned as a *naive* datetime — AEAT does not print a timezone (callers that need UTC must apply Europe/Madrid themselves).
- `src/aeat/application/filing/_builders/` has registered builders for modelos `130`, `303`, `390` only. `get_builder("100")` raises `FilingBuilderError`.
- Every builder (e.g. `Modelo130Builder._materialise_literal`) already fans out every schema casilla to a `FilingValue` with kind `EMPTY` when no input is supplied. So passing an empty inputs dict to `build_draft` yields a draft with modelo + period + profile + every casilla in `EMPTY` state — exactly the scaffold issue `#271` describes.
- `FilingDraft` is frozen and strict; `compute_draft_id` hashes `(modelo, period, profile_tax_id, schema_version, values)` — adding a new optional field that is NOT in the hash input is backwards-compatible.
- `src/aeat/adapters/outbound/aeat/export/_models.py` defines `SubmittedFiling` with `justificante_csv`, `justificante_pdf_path`, `submitted_at`, `status`, `attempts`. `_resolve_original_metadata` in `_complementaria.py` already reads this record (or re-parses the PDF) when Kent later amends.
- `src/aeat/entrypoints/cli/filing/__init__.py` owns the existing `aeat filing build / validate / show / list` sub-app; adding a new `import` command there matches the established convention.

## Period normalisation

AEAT prints periods as printed on the PDF:

| modelo | raw printed period | canonical draft period |
| --- | --- | --- |
| 130 | `1T` / `2T` / `3T` / `4T` (quarterly) | `YYYYQ1..Q4` |
| 303 (monthly filer) | `01..12` | `YYYY-MM` |
| 303 (quarterly filer) | `1T..4T` | `YYYYQ1..Q4` |

The draft builders and the amendment engine (`_period_uses_rectificativa`) already pin on the canonical `YYYYQN` / `YYYY-MM` format. Importing must normalise `(ejercicio, periodo)` into the canonical form so the reconstructed draft is interchangeable with drafts built from scratch.

The justificante's printed ejercicio is today thrown away by `extract_justificante`. Exposing it via a new optional field on `Justificante` is the smallest clean fix.

## What issue #271 explicitly requires vs. what it implies

- **Required (AC)**: reconstructed draft shows in `aeat filing list`; it carries the correct modelo + period + presented_at + csv; no cert auth touched.
- **Implied (for amendment baseline)**: a record wired into the submission-engine lookup (`SubmittedFiling`) so `aeat filing complementaria build` (`#93`) and future amendment wizards (`#234`, `#235`) can treat the import as the baseline submission.

Writing only a draft does satisfy the stated acceptance criteria. However, the amendment flow today resolves metadata off `SubmittedFiling`, not off the draft — so the "baseline for amendment flows" promise requires co-persisting a `SubmittedFiling` with `status=SUBMITTED`, `justificante_csv`, `justificante_pdf_path`, `submitted_at`. That side of the work is cheap (one model construction) and lands the amendment path without follow-ups.

## Open questions resolved

- **Unsupported modelos**: the parser happily reads a Modelo 100 PDF but `get_builder("100")` will raise. The import command must surface a clear "no filing builder registered for modelo X" error rather than a stack trace, and document which modelos are supported.
- **Line-level casilla values not carried in the PDF**: correct — AEAT justificantes record totals, not per-line casilla breakdowns. The command must emit a structured warning so Kent knows to fill casilla values via `aeat filing build` or manually.
- **Timezone**: justificantes stamp Europe/Madrid wall-clock time. The imported `SubmittedFiling.submitted_at` must be converted to UTC before persistence; the draft itself does not need the timestamp.
- **File-not-found**: `parse_justificante` already raises `JustificanteParseError` with a readable message. The CLI must convert that to `typer.BadParameter`.
