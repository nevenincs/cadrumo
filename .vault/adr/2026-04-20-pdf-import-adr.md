---
tags:
  - "#adr"
  - "#pdf-import"
date: "2026-04-20"
modified: '2026-04-20'
related:
  - "[[2026-04-20-pdf-import-research]]"
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
---

# `pdf-import` adr: `reconstruct-filing-draft-from-justificante-pdf` | (**status:** `accepted`)

## Problem Statement

Kent already has a justificante PDF for a Modelo 130 he filed on the AEAT portal before he started using this tool. Issue `#271` requires a cert-free, offline path to pull that past filing into the project: `aeat filing import --from-justificante <path>`. The reconstructed state must let Kent (a) see the past filing in `aeat filing list` and (b) use it as the baseline for the existing amendment flows (`#93`, `#234`, `#235`) without ever touching AEAT certificate authentication.

## Considerations

- The justificante parser (`aeat.domain.justificante.parse_justificante`) is already public, deterministic, and produces a frozen `Justificante` with `modelo`, `period`, `tax_id`, `csv`, `presented_at`, `verification_url`, `source_pdf_path`, `source_pdf_sha256`.
- `Justificante` does not currently surface the `ejercicio` string, but the extractor's `_EJERCICIO_RE` parses it. Period normalisation (`1T` + `2026` → `2026Q1`) requires the ejercicio to be accessible.
- `FilingDraft` is strict + frozen with a content-hashed `draft_id`. The hash covers `modelo`, `period`, `profile_tax_id`, `schema_version`, and `values` only — adding new optional fields that are NOT in the hash is safe.
- Every registered builder (`Modelo130Builder`, `Modelo303Builder`, `Modelo390Builder`) already materialises missing inputs as `FilingValueKind.EMPTY` through `_materialise_literal`. Passing an empty inputs dict yields exactly the "scaffold with every casilla empty" shape the issue requires — no new builder work is needed.
- `get_builder` raises `FilingBuilderError` for unregistered modelos (`100`, `390` without the special inputs contract, etc.). The import command must surface a friendly error rather than a stack trace.
- The amendment flow (`_resolve_original_metadata`) looks up `SubmittedFiling.justificante_csv` / `justificante_pdf_path`, not the draft. For the "baseline for amendment flows" promise the import must co-persist a `SubmittedFiling` with `status=SUBMITTED`.
- AEAT justificantes stamp Europe/Madrid wall-clock time with no timezone marker. `SubmittedFiling.submitted_at` must be UTC-normalised for consistency with other project records.
- `@pytest.mark.unit` + `@pytest.mark.domain_financial_input` markers fit the subpackage scope (Kent-visible financial-input ingestion).

## Constraints

- **Zero cert coupling.** No import path may reference `aeat.adapters.outbound.aeat.auth`, `aeat.adapters.outbound.aeat.export._submitters`, or any live-submission code path.
- **No live-submit surface regression.** The import command registers under `aeat filing`, not under `aeat submission`; it must not call `SubmissionEngine.submit*` or touch `live_transport_supported`.
- **Pydantic strict + frozen** throughout — no bare dicts at boundaries.
- **`AeatError`-rooted exceptions** (`JustificanteParseError`, `FilingBuilderError`) surface to Typer via `typer.BadParameter`.
- **No mocks, patches, stubs, fakes** in the new tests — we use the committed synthetic fixture PDFs under `tests/fixtures/justificantes/`.
- **Trilingual** where applicable: warning messages use `Translatable` only when they cross a typed boundary; ephemeral CLI echo is English for now (matches existing `aeat filing build` output).

## Implementation

### 1. Expose `ejercicio` on `Justificante`

`aeat.domain.justificante._schema.Justificante` gains `ejercicio: str | None = Field(default=None, max_length=8)`. `aeat.domain.justificante._extract.extract_justificante` populates it from the existing `_EJERCICIO_RE` match when present. Additive; no parser-side breakage.

### 2. New `aeat.application.filing._import` module

`src/aeat/application/filing/_import.py` owns the reconstruction helper:

```python
@dataclass(frozen=True)
class JustificanteImportResult:
    draft: FilingDraft
    submission: SubmittedFiling
    warnings: tuple[Translatable, ...]

def import_filing_from_justificante(
    pdf_path: Path,
    *,
    schema_provider: CasillaSchemaProvider,
    now: datetime | None = None,
) -> JustificanteImportResult: ...
```

Behaviour:

- `parse_justificante(pdf_path)` → `Justificante`.
- Normalise period: `_normalise_period(modelo, ejercicio, raw_period) -> str` returning the canonical form. Modelo-specific table — `1T..4T` → `YYYYQ1..Q4`; numeric months → `YYYY-MM`; `0A` → `YYYY` for annual modelos.
- Build a `FilingOperatorProfile(tax_id=j.tax_id, display_name=f"Imported filing {j.csv}", applicable_modelos=(j.modelo,))`.
- Call `build_draft(modelo=..., period=..., profile=..., inputs={}, schema_provider=schema_provider)`. Warnings emitted by the validator for the all-empty shape are retained — Kent sees them in `aeat filing show`.
- Construct `SubmittedFiling` with:
    - `submission_id = sha256(j.csv + ":" + draft.draft_id)[:16]` (deterministic; avoids collision with live-submission ids that hash `(draft_id, attempt_ordinal)`).
    - `draft_id = draft.draft_id`.
    - `status = SUBMITTED`.
    - `justificante_csv = j.csv`.
    - `justificante_pdf_path = j.source_pdf_path.resolve()`.
    - `submitted_at` = `j.presented_at` converted from Europe/Madrid wall-clock to UTC (`zoneinfo.ZoneInfo("Europe/Madrid")` → `.astimezone(UTC)`).
    - Single `SubmissionAttempt` stamped with the same timestamps and `status=SUBMITTED`.
- Emit at minimum one warning: *"Line-level casilla values were not extracted from the justificante PDF; fill them via `aeat filing build` or directly in the draft JSON."* Wrapped in a `Translatable` so callers can render in Spanish/English/Hungarian later (`aeat.core.i18n.Translatable`).

### 3. Wire the CLI

`src/aeat/entrypoints/cli/filing/__init__.py` adds:

```python
@app.command("import")
def import_(
    from_justificante: Annotated[Path, typer.Option("--from-justificante", ...)],
) -> None: ...
```

The command resolves the PDF, calls `import_filing_from_justificante`, persists the draft via the existing `_save_draft`, persists the submission JSON under `settings.aeat_submissions_dir`, prints the warning(s), and renders the draft via `_render_draft`.

Error handling:

- Missing or unreadable PDF → `typer.BadParameter`.
- `JustificanteParseError` / `JustificanteCsvNotFoundError` → `typer.BadParameter` preserving the parser message.
- Unsupported modelo (no builder registered) → `typer.BadParameter(f"modelo {modelo} is not supported for import yet; registered: {...}")`.

### 4. Tests (all `@pytest.mark.unit`)

- `src/aeat/application/filing/test_import.py` — unit tests against the committed `modelo_130_2026Q1.pdf` and `modelo_303_2026Q1.pdf` fixtures. Asserts:
    - Draft has `modelo == "130"`, `period == "2026Q1"`, `profile_tax_id == "00000000T"`, every casilla is `FilingValueKind.EMPTY`.
    - `SubmittedFiling.justificante_csv == "ABCD1234EFGH5678"`; `submitted_at.tzinfo is UTC`; `status == SUBMITTED`.
    - Period normalisation covers 130/303 quarterly, and a fabricated monthly 303 path (via a parametrised helper — not a new fixture — to keep the PDF fixture corpus stable).
    - Unsupported modelo (Modelo 100 fixture) raises `FilingBuilderError` with a readable message.
    - Missing PDF raises `JustificanteParseError` (from `parse_justificante`).
- `src/aeat/entrypoints/cli/filing/test_filing_cli.py` — smoke tests for `aeat filing import`:
    - Happy path: command exits 0, draft JSON is created under `AEAT_DRAFTS_DIR`, submission JSON is created under `AEAT_SUBMISSIONS_DIR`, output contains the warning string.
    - Missing PDF → exit code `2` (`BadParameter`).

### 5. Documentation

- `docs/coverage/kent-capabilities.md` — new row for "import past filing from justificante PDF".
- No user-facing doc regeneration requested in this scope.

### 6. Forbidden / explicitly out of scope

- No changes to `aeat.adapters.outbound.aeat.auth`, `aeat.adapters.outbound.aeat.export._submitters`, or `SubmissionEngine` wiring.
- No changes to live-submission env gates or the 4-factor safety charter.
- No changes to amendment engine (`_complementaria.py`) beyond what `SubmittedFiling` already supports. The amendment flow will "just work" against imported records because it resolves metadata from `SubmittedFiling.justificante_csv` / `justificante_pdf_path`, both of which we populate.

## Consequences

- Kent can run `aeat filing import --from-justificante path/to/receipt.pdf` and immediately see the draft in `aeat filing list`; the same draft doubles as the amendment baseline for `#234` / `#235`.
- `Justificante` gains one optional field (`ejercicio`). JSON records without the field round-trip unchanged because the field defaults to `None`.
- A new persisted `SubmittedFiling` with `status=SUBMITTED` is created *without* any AEAT network call, which is a deliberate re-use of the existing post-submission record shape — this record is the declared source of truth for "a filing that exists at AEAT" and tastes exactly like one we submitted ourselves (because Kent's earlier manual submission did).
- Warning messaging is added but no behaviour is wired to block filing flows on it — Kent fills the casillas later.
- No tests are skipped, no lint rules are suppressed, no authentication code is touched.
