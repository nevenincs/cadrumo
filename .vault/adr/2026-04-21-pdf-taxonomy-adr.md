---
tags:
  - "#adr"
  - "#pdf-taxonomy"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-pdf-taxonomy-research]]"
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
  - "[[2026-04-12-justificante-parser-adr]]"
  - "[[2026-04-20-pdf-import-adr]]"
---

# `pdf-taxonomy` adr: `name-and-scope-every-aeat-pdf-the-project-ingests` | (**status:** `accepted`)

## Problem Statement

The project's only PDF parser (`aeat.domain.justificante`) reads AEAT *justificantes de presentación* — filing receipts that, by design, carry metadata and totals but **no per-casilla values**. The shipped `#271` import command reflects that scope correctly, but downstream consumers (user, EPIC #233, the "import past filings" narrative) conflate receipt import with full filing-copy import. Before we scope casilla-complete import, extractors, fixture corpora, or calculation verification, we need one authoritative vocabulary that names every AEAT-produced PDF the project will ingest and states explicitly which Kent workflow each one serves.

## Considerations

- Kent encounters six distinct PDF classes from AEAT: *justificante de presentación*, *declaración* (filing copy), *borrador* (pre-filing draft — Renta primarily), *predeclaración / simulación* (pre-filing preview), *datos fiscales* (informational inputs), *datos personales* (identity boilerplate). Only the first four are filing-shaped; only three of those (declaración, borrador, predeclaración) carry per-casilla values.
- The project mandate pins Spanish as the authoritative AEAT terminology. Keeping the original Spanish names at module level (`aeat.domain.justificante`, `aeat.adapters.inbound.declaracion`, `aeat.adapters.inbound.borrador`, …) is idiomatic and stable across AEAT template revisions.
- `aeat.domain.justificante` is already a public surface (re-exported from `aeat.application.filing._import` via `parse_justificante`, referenced by the `SubmittedFiling` amendment baseline, used by `_complementaria._resolve_original_metadata`). Renaming it mid-flight breaks the amendment flow. Preserving the name is the lower-risk path.
- The CLI already registers `aeat filing import --from-justificante`. That subcommand is in-scope for the amendment-baseline narrative. A casilla-complete import needs a **sibling** flag (`--from-declaracion`, `--from-borrador`, `--from-predeclaracion`), not a replacement.
- The coverage matrices (`docs/coverage/modelos.md`, `docs/coverage/kent-capabilities.md`) track per-modelo state by capability. A new axis — "which PDF class does the import understand for this modelo" — is additive.
- `FilingValue.kind` already enumerates `LITERAL | COMPUTED | INHERITED | DEFAULT | EMPTY`. None of these quite fit "value imported from a PDF the user supplied." A new enum value `IMPORTED` (or reusing `LITERAL` with a distinct `source` string) is a downstream decision for cluster D; this ADR only locks vocabulary, not `FilingValueKind`.

## Constraints

- **Zero breakage of shipped `#271` contracts.** `aeat.domain.justificante` keeps its name, shape, and public surface. `aeat filing import --from-justificante` keeps its behaviour.
- **Zero cert-auth coupling.** All documents in scope are user-local (Kent downloaded them from Sede).
- **Spanish module names** for PDF-class packages (`aeat.adapters.inbound.declaracion`, etc.) — consistent with project mandate.
- **Strict+frozen pydantic v2** for every new boundary record.
- **Errors rooted at `AeatError`.** New `DeclaracionParseError` / `BorradorParseError` / `PredeclaracionParseError` inherit from a common `PdfFilingImportError(AeatError)` defined once.
- **Trilingual `Translatable`** for any user-facing labels (per project mandate).
- **Test markers** `@pytest.mark.unit` module-level; `@pytest.mark.domain_financial_input` for import-side work.
- **No mocks / fakes / stubs** in live tests; synthetic PDFs allowed for unit tests per the `#271` precedent.

## Implementation

### 1. Canonical vocabulary

Adopt and document these names as the project's authoritative vocabulary. All future ADRs, plans, issues, and coverage-matrix rows MUST use them.

| ES name | Project module (planned) | Project pydantic record | Carries casillas? | Carries CSV? |
| --- | --- | --- | --- | --- |
| justificante de presentación | `aeat.domain.justificante` ✅ (exists) | `Justificante` ✅ (exists) | No | Yes |
| declaración / copia de la declaración | `aeat.adapters.inbound.declaracion` (cluster D) | `DeclaracionFiling` (cluster D) | Yes | Yes |
| borrador | `aeat.adapters.inbound.borrador` (cluster F) | `BorradorFiling` (cluster F) | Yes | No |
| predeclaración / simulación | `aeat.predeclaracion` (cluster F) | `PredeclaracionFiling` (cluster F) | Yes | No |
| datos fiscales | `aeat.datos_fiscales` (out of scope for import; candidate for `aeat filing build` input wizard) | `FiscalDataStatement` (later) | N/A (inputs, not casillas) | No |
| datos personales | Out of scope. Identity/profile data belongs in `AutonomoProfile`, not PDF import. | — | — | — |

### 2. CLI surface — additive flags

The existing `aeat filing import --from-justificante <PATH>` stays. Additive flags land in cluster D / F:

- `aeat filing import --from-declaracion <PATH>` → casilla-complete filing-copy import (cluster D).
- `aeat filing import --from-borrador <PATH>` → casilla-complete borrador import (cluster F; Renta primarily).
- `aeat filing import --from-predeclaracion <PATH>` → casilla-complete simulation import (cluster F; non-binding).

Any two flags at once → `typer.BadParameter("only one --from-* flag at a time")`. Exactly zero of them (command invoked bare) → help text.

### 3. Shared module skeleton

Each new PDF-class module mirrors `aeat.domain.justificante`'s proven shape:

```
src/aeat/<class>/
    __init__.py          # public API: parse_<class>, record class, errors
    _schema.py           # strict+frozen pydantic record (modelo, período, ejercicio,
                         # tax_id, values: tuple[ExtractedCasilla, ...] , …)
    _extract.py          # regex / layout-anchor extractor
    _errors.py           # <Class>ParseError(PdfFilingImportError(AeatError))
    _parsers/            # backend plugins (pdfplumber default; pypdf for AcroForm/XFA)
        _pdfplumber_backend.py
    test_parser.py       # unit tests against committed fixtures
```

A shared record fragment factors out what every casilla-carrying class needs:

```python
# src/aeat/adapters/inbound/pdf/_shared.py  (new)

class ExtractedCasilla(BaseModel):
    """One casilla ID + printed value extracted from a filing PDF."""
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: str
    printed_value: Decimal | str | None
    source_page: int
    source_bbox: tuple[float, float, float, float] | None = None  # pdfplumber bbox
    extraction_confidence: float  # 0.0–1.0; reserved for cluster D fallback logic
```

### 4. Shared error hierarchy

```
AeatError (existing)
└── PdfFilingImportError (new, under src/aeat/adapters/inbound/pdf/_errors.py)
    ├── JustificanteError (existing; re-homed as subclass — no behaviour change)
    ├── DeclaracionParseError
    ├── BorradorParseError
    └── PredeclaracionParseError
```

Re-homing `JustificanteError` is a compatibility-preserving refactor: callers that catch `JustificanteError` keep catching it; callers that catch `AeatError` keep catching it; callers that want "any PDF import error" get the new `PdfFilingImportError` as the unifying type.

### 5. Coverage-matrix axis

Add a new column to `docs/coverage/modelos.md`:

| Modelo | … existing columns … | `aeat.domain.justificante` | `aeat.adapters.inbound.declaracion` | `aeat.adapters.inbound.borrador` | `aeat.predeclaracion` |

Each cell: ❌ / 🚧 / ✅ with the same semantics as existing columns. This gives every future cluster a concrete deliverable grid.

### 6. Documentation

- Add a vocabulary section to `CONTRIBUTING.md` or a new `docs/concepts/aeat-pdfs.md` — one paragraph per PDF class with an example file name and a sentence on when Kent would use it.
- Update EPIC `#233` title / description to disambiguate receipt import from filing-copy import; split children accordingly.

### 7. Explicitly out of scope

- Any actual parser / extractor code for `aeat.adapters.inbound.declaracion`, `aeat.adapters.inbound.borrador`, `aeat.predeclaracion`, `aeat.datos_fiscales` — those are clusters D, F, and later.
- Renaming or moving `aeat.domain.justificante`. Name, shape, and public surface are locked.
- Changes to `aeat filing import --from-justificante`. Behaviour is locked at the `#271` shipped contract.
- Changes to `FilingValueKind`. Cluster D will revisit.
- Changes to `SubmittedFiling` or the amendment-baseline flow. They remain receipt-anchored.

## Consequences

- Every subsequent vaultspec document uses a single authoritative vocabulary; the "what PDF is this?" question stops recurring.
- The coverage matrix gains a concrete per-modelo / per-PDF-class grid that clusters B–H can tick off.
- `aeat.domain.justificante` keeps its name and public surface — `#271` ships unchanged, the amendment-baseline flow keeps working.
- Cluster D gets a one-page skeleton to replicate per new PDF class, instead of reinventing the module layout each time.
- The shared `ExtractedCasilla` record pins the extractor output shape across clusters D, E, F — cluster E's verification pass has one type to consume.
- The shared `PdfFilingImportError` root lets CLI surfaces (cluster D onward) catch and translate all PDF-import errors uniformly, without leaking backend specifics.
- EPIC `#233` gains clarity: one child per PDF class, not one child per "import past filing" vague title.
