---
tags:
  - "#audit"
  - "#real-pdf-import"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-pdf-taxonomy-plan]]"
  - "[[2026-04-21-justificante-reframing-plan]]"
  - "[[2026-04-21-casilla-schema-completeness-plan]]"
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
---

# real-pdf-import execution wave 1 — code review audit

## Scope

Three EPIC-#305 clusters executed end-to-end in the `feature/271-pdf-import` worktree:

- **Cluster A** (PDF taxonomy scaffolding) — new `src/aeat/adapters/inbound/pdf/` package (`ExtractedCasilla`, `PdfFilingImportError`) + `docs/concepts/aeat-pdfs.md` + re-home of `JustificanteError` under `PdfFilingImportError`.
- **Cluster G** (justificante reframing — code part) — `src/aeat/domain/justificante/test_vocabulary_stable.py` public-surface pin + EPIC #233 title polish.
- **Cluster B phase 1** (schema provenance extension) — `CasillaSource` pydantic record + optional `sources` / `valid_from` / `valid_to` fields on `StaticCasillaSchema` + parametrised `test_schema_completeness.py` (pass for 303; xfail strict for 130 until phase 2 completes the corpus).

## Review outcome

**APPROVED WITH FIXES APPLIED.** The `vaultspec-code-reviewer` persona surfaced one HIGH finding (coverage matrices not updated per plan step 4); that finding has been addressed in the same wave before commit (see Findings §H1 below).

## Findings

### H1 — Coverage matrices not updated (HIGH, **fixed**)

- Plan `2026-04-21-pdf-taxonomy-plan.md` step 4 mandates four new columns on `docs/coverage/modelos.md` (`justificante` / `declaración` / `borrador` / `predeclaración` import) and three new rows on `docs/coverage/kent-capabilities.md` (past-filing / borrador / predeclaración import).
- Reviewer flagged the files had not been touched.
- **Resolution**: edited both files in this execution wave with the plan's specified values. Modelos matrix now has 14 columns; Kent capabilities gains five new rows (justificante shipped ✅; declaración / borrador / predeclaración / verdict 🚧 under #305). Plan step 4 is now green.

### M1 — Concepts doc uses `../../.vault/...` relative Markdown links (MEDIUM, deferred)

Works with the current repo layout but will break if the doc moves. Deferred to the next doc refactor; tracked only if the doc ever moves.

### M2 — `CasillaSource.url` is bare `str | None` (MEDIUM, deferred)

Every other field is tightly validated; the URL is permissive. A `HttpUrl` or regex constraint would match the `Justificante.verification_url` convention. Acceptable for phase 1; tighten in phase 2 when corpora are generated from URL-fetched sources.

### M3 — `test_schema_completeness.py` parametrises over `año` then `del año` (MEDIUM, accepted)

The year is held in the test identity for future per-año schema versioning but currently unused by assertion body. Documented via inline comment. Flips to active use when cluster B phase 2 introduces `valid_from` / `valid_to` matching per `(modelo, año)` tuples.

### L1 — `_pdf_import` underscore-prefixed but `PdfFilingImportError` will surface in tracebacks (LOW)

Traceback readability impacted marginally. Consider promoting to `aeat.pdf_import` in a later cleanup.

### L2 — Two inheritance tests in `test_parser.py` use local imports in the test body (LOW)

`from .._pdf_import import PdfFilingImportError` inside the test body rather than module-level. Stylistic; no functional impact.

## Clean areas (informational)

- No mocks / stubs / fakes / patches in any new unit test.
- Every new test module carries `pytestmark = [pytest.mark.unit, pytest.mark.domain_*]` at module level.
- All relative imports inside `src/aeat/`; no `aeat.*` absolute drift.
- `issubclass(JustificanteError, AeatError)` preserved and guarded by a new unit test.
- `aeat.domain.justificante.__all__` frozen-set pinned by `test_vocabulary_stable.py`.
- `SubmittedFiling.justificante_csv` / `justificante_pdf_path` untouched.
- `aeat filing import --from-justificante` behaviour unchanged; `test_filing_cli.py` still green.
- `ExtractedCasilla`, `CasillaSource`, `PdfFilingImportError` all strict+frozen+`extra="forbid"`.
- `xfail(strict=True)` reasons on `test_schema_completeness.py` enumerate the exact missing casilla IDs (09, 11, 12, 14, 17, 19) so the test becomes green of its own accord when phase 2 closes.
- No PII / real NIFs in any fixture or test.
- No `# removed:` / `# TODO(remove later):` scaffolding comments.
- All six ADR targets referenced by `docs/concepts/aeat-pdfs.md` exist under `.vault/adr/`.

## Kent UX roleplay (cluster A / G / B phase 1 — scaffolding only)

Kent directly observes nothing from this wave. Acceptance is developer-observable:

- `from aeat.adapters.inbound.pdf import ExtractedCasilla, PdfFilingImportError` imports cleanly — ✅ verified in `test_shared.py`.
- `issubclass(aeat.domain.justificante.JustificanteError, aeat.adapters.inbound.pdf.PdfFilingImportError) is True` — ✅ verified in `test_parser.py::TestJustificanteErrorRehome`.
- `aeat.domain.justificante.__all__` retains every frozen symbol — ✅ verified in `test_vocabulary_stable.py`.
- `docs/concepts/aeat-pdfs.md` renders the six-PDF-class taxonomy with one paragraph per class — ✅ present.
- `docs/coverage/modelos.md` + `docs/coverage/kent-capabilities.md` carry the new import axes — ✅ present after H1 fix.
- Every existing `aeat filing import --from-justificante` workflow still runs — ✅ verified by the existing `test_filing_cli.py` suite (unchanged; all green).

## Quality gates

- `uv run ruff check src/aeat/adapters/inbound/pdf/ src/aeat/domain/justificante/ src/aeat/application/filing/ docs/concepts/` — clean.
- `uv run ty check src/aeat/adapters/inbound/pdf/ src/aeat/domain/justificante/ src/aeat/application/filing/` — clean.
- `uv run pytest -m unit src/aeat/adapters/inbound/pdf/ src/aeat/domain/justificante/ src/aeat/application/filing/` — 96 passed, 2 deselected, 2 xfailed (intentional: Modelo 130 schema completeness).

## Decision

Wave 1 is **ready to commit** on the `feature/271-pdf-import` branch. No regressions to the `#271` shipping contract. Next wave (cluster C scaffolding) proceeds.
