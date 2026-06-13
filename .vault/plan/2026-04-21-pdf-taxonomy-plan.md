---
tags:
  - "#plan"
  - "#pdf-taxonomy"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-pdf-taxonomy-adr]]"
  - "[[2026-04-21-pdf-taxonomy-research]]"
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
---

# `pdf-taxonomy` plan: adopt the canonical AEAT-PDF vocabulary without breaking `#271`

## Goal

Land the vocabulary, shared types, shared error hierarchy, and coverage-matrix axis defined in `2026-04-21-pdf-taxonomy-adr`. **No parser code.** The cluster ships the scaffolding that clusters B–H consume.

## Step 1 — Add `src/aeat/adapters/inbound/pdf/` shared module

**New directory**: `src/aeat/adapters/inbound/pdf/`.

Files:

- `src/aeat/adapters/inbound/pdf/__init__.py` — public surface re-exports `ExtractedCasilla`, `PdfFilingImportError`.
- `src/aeat/adapters/inbound/pdf/_shared.py` — `ExtractedCasilla` pydantic v2 record exactly as in the ADR §3.
- `src/aeat/adapters/inbound/pdf/_errors.py` — `PdfFilingImportError(AeatError)` root.
- `src/aeat/adapters/inbound/pdf/test_shared.py` — unit tests:
    - module-level markers `pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]`
    - `ExtractedCasilla` is strict+frozen (mutation raises `ValidationError`)
    - extra fields rejected
    - `extraction_confidence` outside `[0.0, 1.0]` rejected (add `Field(ge=0.0, le=1.0)`)
    - `source_bbox` accepts a 4-tuple of floats; rejects other shapes
    - `printed_value` accepts `Decimal`, `str`, `None` and round-trips through `model_dump_json` / `model_validate_json`

Relative-imports only (`from ..errors import AeatError`).

## Step 2 — Re-home `JustificanteError`

**Edit** `src/aeat/domain/justificante/_errors.py`:

```python
from .._pdf_import._errors import PdfFilingImportError

class JustificanteError(PdfFilingImportError):
    ...
```

No changes to subclasses. `AeatError` remains the grand-parent so every existing `except AeatError` call site keeps catching.

**Tests**: add one assertion in `src/aeat/domain/justificante/test_parser.py` (TestJustificanteModel):

```python
def test_justificante_error_is_pdf_filing_import_error(self) -> None:
    from .._pdf_import import PdfFilingImportError
    assert issubclass(JustificanteError, PdfFilingImportError)
```

## Step 3 — Expose the shared surface from `aeat`

**Edit** `src/aeat/__init__.py` only if it exports error types today (check first). If not, skip — shared types are accessed via `aeat.adapters.inbound.pdf` directly.

## Step 4 — Coverage-matrix axis

**Edit** `docs/coverage/modelos.md`:

- Add four columns after the existing submission-engine columns:
    - `aeat.domain.justificante` (receipt metadata import)
    - `aeat.adapters.inbound.declaracion` (filing-copy casilla import)
    - `aeat.adapters.inbound.borrador` (pre-filing draft import — Renta)
    - `aeat.predeclaracion` (simulation import)
- For every row:
    - `aeat.domain.justificante`: ✅ for 100, 130, 303 (fixtures shipped); 🚧 for everything else.
    - Remaining three columns: all ❌ at this moment — clusters D/F will fill them.

**Edit** `docs/coverage/kent-capabilities.md`:

- Add a row "Kent imports a past filing from its filing-copy PDF" — all ❌ today; this is what cluster D delivers.
- Add a row "Kent imports a pre-filing borrador for modelo 100" — all ❌ today; this is cluster F.
- Add a row "Kent imports a filing simulation (predeclaración)" — all ❌ today.

## Step 5 — Concepts doc

**New file**: `docs/concepts/aeat-pdfs.md`.

- One H2 per PDF class from the ADR §1 table. For each: one paragraph describing what it is, when Kent gets it, and which import flow (if any) consumes it.
- Explicit "**Not an import source:**" note for *datos fiscales* and *datos personales* so future contributors don't spawn extractor modules for them.

## Step 6 — EPIC `#233` hygiene

- Add a comment on `#233` disambiguating receipt import (shipped via `#271`) from filing-copy import (this umbrella).
- Re-title `#233` to "Kent imports past filings (umbrella)" if the current title is ambiguous.
- Do **not** close `#233`; it remains the tracker.
- Create / confirm child issues for clusters D, F, G as tracked sub-EPICs under `#233`.

## Step 7 — Lint, type-check, test

- `uv run ruff check src/aeat/adapters/inbound/pdf/ src/aeat/domain/justificante/` — clean.
- `uv run ty check src/aeat/adapters/inbound/pdf/ src/aeat/domain/justificante/` — clean.
- `uv run pytest -m unit src/aeat/adapters/inbound/pdf/ src/aeat/domain/justificante/` — green (the existing 12 justificante tests + the new shared-module unit tests).

## Step 8 — Docs build smoke

If `docs/` is built via a docs-generator, run the local build once to catch broken wiki-links. Otherwise skip.

## Step 9 — Commit, PR

- One commit: `feat(pdf-import): adopt canonical AEAT-PDF vocabulary + shared types`.
- PR title: "feat(pdf-import): canonical AEAT-PDF vocabulary + shared types (cluster A)".
- PR body references the umbrella + cluster-A research + ADR wiki-links and lists deliverables per step above.
- Labels: `type:refactor`, `domain:financial-input`, `area:submission` (or `area:import` if it exists), `priority:P1-high`, `effort:S`, `parallel-safe`.

## Non-goals for this cluster

- **No parser code.** Clusters D, F deliver that.
- **No changes to `aeat.domain.justificante` public API.** Only the error base class moves.
- **No changes to `aeat filing import --from-justificante`.** Behaviour locked.
- **No `aeat.adapters.inbound.declaracion` / `aeat.adapters.inbound.borrador` / `aeat.predeclaracion` / `aeat.datos_fiscales` directories created.** They come with their cluster.
- **No updates to `FilingValueKind`.** Cluster D revisits.

## Acceptance (Kent-observable)

Kent doesn't see anything change from this cluster — it is pure scaffolding for the downstream clusters. The acceptance criterion is **developer-observable**:

- `from aeat.adapters.inbound.pdf import ExtractedCasilla, PdfFilingImportError` imports cleanly.
- `issubclass(aeat.domain.justificante.JustificanteError, aeat.adapters.inbound.pdf.PdfFilingImportError) is True`.
- `docs/coverage/modelos.md` renders with the four new columns; per-row values match the ADR's scope statement.
- `docs/concepts/aeat-pdfs.md` exists and distinguishes the six PDF classes.
