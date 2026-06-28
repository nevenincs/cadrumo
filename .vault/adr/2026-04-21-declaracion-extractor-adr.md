---
tags:
  - "#adr"
  - "#declaracion-extractor"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-declaracion-extractor-research]]"
  - "[[2026-04-21-pdf-taxonomy-adr]]"
  - "[[2026-04-21-casilla-schema-completeness-adr]]"
  - "[[2026-04-21-real-pdf-fixture-corpus-adr]]"
---

# `declaracion-extractor` adr: `label-first-bbox-fallback-acroform-opportunistic-per-modelo-registry` | (**status:** `superseded`)

## Superseded (2026-05-21)

This ADR is **superseded by `2026-05-21-declaracion-extraction-architecture-adr`**.
Its `DeclaracionExtractor` ABC + per-modelo Python extractor-class
registry was never going to survive the registry-data direction of
`2026-05-03-calculation-truth-registry-pending-adr`: the hexagonal
restructure deleted every extractor class and replaced them with a
registry-profile-driven generic parser. The successor ADR ratifies that
registry-driven design as canonical and adds a typed named-field
extraction primitive. The decision content below is retained for
historical context only; do not implement the `DeclaracionExtractor`
ABC or the per-modelo class registry.

## Problem Statement

Cluster D delivers the `aeat.adapters.inbound.declaracion` module — a per-modelo extractor that turns a *copia de la declaración* PDF into a strict `DeclaracionFiling` record with every casilla ID + printed value identified, ready for cluster E's round-trip calc verification. The module must be reliable across AEAT template revisions, survive intra-año form amendments, produce deterministic output for the synthetic L3 generator, and degrade gracefully (partial extraction > hard failure).

## Considerations

- Three extraction primitives are viable: label-anchored regex (simplest, fastest, 90 % coverage), bbox-anchored (resilient, maintenance-heavy), AcroForm reader (narrow applicability but cheap to try). OCR is an escape hatch for scans but out of MVP scope.
- AEAT template revisions drift mid-año (Orden HAC/819/2024 re-numbered Modelo 303 casillas 2024-09). The registry must key on `(modelo, template_revision)`, not just `(modelo, año)`.
- The existing `aeat.domain.justificante._extract` helpers (`_parse_decimal`, `_strip_accents`, `_require`) are directly reusable — promoted to the shared `_pdf_import/_shared.py` module cluster A opens.
- `aeat.application.filing.build_draft(..., inputs=extracted_casillas_dict, ...)` is the right pairing point: the extractor produces casilla-ID-keyed literals; `build_draft` materialises the computed casillas on top; cluster E then re-runs the formula engine over everything and diffs.
- The `Engine.audit_against` primitive expects a ruleset. Extractor output for a modelo-with-no-ruleset (390 today) can still flow through `build_draft` but cluster E cannot verify — the CLI reports `EXTRACTION_OK, VERIFICATION_UNAVAILABLE`.
- Project mandate: Pydantic v2 strict+frozen boundary records; no bare dicts; `AeatError`-rooted exceptions; Spanish CLI flag names.
- Kent-observable AC: `aeat filing import --from-declaracion <pdf>` produces a draft whose casilla tuple matches the printed values; any casilla the extractor could not resolve surfaces as a warning with a readable explanation.

## Constraints

- **Zero cert coupling.** Extraction is pure file I/O.
- **Zero live-submit coupling.** This cluster adds no path to `SubmissionEngine.submit*`.
- **Strict+frozen pydantic v2** for every record (`DeclaracionFiling`, `ExtractedCasilla`, `ExtractionWarning`, `TemplateRevision`, `ExtractorRegistryKey`).
- **Errors** inherit `DeclaracionParseError < PdfFilingImportError < AeatError`.
- **Backend plurality** — `_parsers/_pdfplumber_backend.py` is default; `_parsers/_pypdf_backend.py` ships for AcroForm lookups. No other PDF dependency.
- **Tests**: unit markers `@pytest.mark.unit, @pytest.mark.domain_financial_input`, `fixture_tier_l3` for synthetic-only tests; `fixture_tier_l1` / `l2` marks any real-anchor tests.
- **Deterministic output** — identical input PDF bytes → identical `DeclaracionFiling` output; no datetime in the hash.

## Implementation

### 1. `aeat.adapters.inbound.declaracion` module layout

```
src/aeat/adapters/inbound/declaracion/
    __init__.py           # re-exports DeclaracionFiling, parse_declaracion,
                          # DeclaracionParseError, TemplateRevision
    _schema.py            # DeclaracionFiling, ExtractionWarning, TemplateRevision
    _errors.py            # DeclaracionParseError < PdfFilingImportError
    _extract.py           # Primitives P1 (regex), P2 (bbox), P3 (AcroForm)
    _extractor.py         # DeclaracionExtractor ABC
    _detect.py            # detect_template_revision(pdf_path)
    _extractors/
        __init__.py       # registry keyed by TemplateRevision
        modelo_130_v2025.py
        modelo_303_v2024_2.py   # post-September 2024 numbering
        modelo_303_v2025.py
        (additional concrete extractors ship with their own issues)
    _parsers/
        _pdfplumber_backend.py  # P1 and P2 backing
        _pypdf_backend.py       # P3 backing
    test_extractor.py
```

### 2. Public API

```python
# src/aeat/adapters/inbound/declaracion/__init__.py

def parse_declaracion(
    pdf_path: Path,
    *,
    modelo_override: str | None = None,
    template_revision_override: str | None = None,
) -> DeclaracionFiling: ...
```

### 3. Strict records

```python
class TemplateRevision(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    modelo: str
    año: int
    revision: str                  # e.g., "2024.09" for 303 post-HAC/819
    detected_from: Literal["header", "footer", "filename", "explicit_override"]

class ExtractionWarning(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    casilla_id: str | None
    code: str                      # e.g., "casilla-not-found", "ambiguous-label"
    message: Translatable
    primitive_attempted: Literal["acroform", "label_regex", "bbox", "ocr"]

class DeclaracionFiling(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str
    period: str                    # canonical: 2026Q1 / 2026-01 / 2026A
    ejercicio: str                 # YYYY
    tax_id: str
    template_revision: TemplateRevision
    values: tuple[ExtractedCasilla, ...]           # cluster A type
    warnings: tuple[ExtractionWarning, ...]
    source_pdf_path: Path
    source_pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parsed_at: datetime
    extraction_status: Literal["complete", "partial", "failed"]
```

`extraction_status` = `complete` when every required casilla (per cluster-B corpus) is present; `partial` when ≥ 50 % of required casillas resolved; `failed` when below.

### 4. `DeclaracionExtractor` ABC

```python
class DeclaracionExtractor(ABC):
    template_revision: ClassVar[TemplateRevision]

    @abstractmethod
    def extract(self, pdf_path: Path) -> DeclaracionFiling: ...
```

Registry in `_extractors/__init__.py` keyed by `(modelo, año, revision)`. Missing tuple → `DeclaracionParseError` with a "no extractor registered; supported: …" message.

### 5. Primitive stack (ordered)

For every registered extractor the default implementation is:

```python
def extract(self, pdf_path: Path) -> DeclaracionFiling:
    # P3 — AcroForm first (cheap; near-zero false positives)
    if acroform_readable(pdf_path):
        tuples = read_acroform(pdf_path, field_map=self.acroform_field_map)
        if tuples and self._covers_required(tuples):
            return self._finalise(pdf_path, tuples, primitive="acroform")

    # P1 — label-anchored regex
    text = extract_text(pdf_path)
    p1_tuples = apply_label_regex(text, self.label_regex_map)
    if self._covers_required(p1_tuples):
        return self._finalise(pdf_path, p1_tuples, primitive="label_regex")

    # P2 — bbox-anchored fallback
    words = extract_words(pdf_path)
    p2_tuples = apply_bbox_extraction(words, self.bbox_map)

    merged = self._merge(p1_tuples, p2_tuples)
    return self._finalise(pdf_path, merged, primitive="merged")
```

`_finalise` attaches extraction warnings for any required casilla still missing, sets `extraction_status`, and computes SHA-256 of the source bytes.

### 6. Detection

`detect_template_revision(pdf_path)` reads the first page text; regex extracts the AEAT form code marker (`"Modelo 303 — Ejercicio 2025 — Período 1T"` or footer revision stamp). On ambiguity returns `None`; caller falls back to explicit override or raises.

### 7. MVP delivery order

1. **Modelo 130, 2025 revision** — smallest corpus (19 casillas), reuses existing ruleset.
2. **Modelo 303, 2024 post-Sept revision** — tests the template-revision split.
3. **Modelo 303, 2025 revision**.
4. Later clusters add 111, 115, 180, 190; Modelo 100 is cluster F.

Each concrete `modelo_N_vY.py` ships as its own PR, fully code-reviewed and verified against cluster-C L3 synthetic + any L1 anchors, before the next lands.

### 8. CLI wiring (cluster-A additive flag materialised here)

`src/aeat/entrypoints/cli/filing/__init__.py`:

```python
@app.command("import")
def import_(
    from_justificante: Annotated[Path | None, typer.Option(...)] = None,
    from_declaracion: Annotated[Path | None, typer.Option(...)] = None,
    modelo: Annotated[str | None, typer.Option("--modelo", ...)] = None,
    año: Annotated[int | None, typer.Option("--año", ...)] = None,
) -> None:
    if sum(bool(x) for x in (from_justificante, from_declaracion)) != 1:
        raise typer.BadParameter("exactly one --from-* flag is required")
    if from_declaracion:
        return _handle_declaracion_import(from_declaracion, modelo=modelo, año=año)
    return _handle_justificante_import(from_justificante)
```

`_handle_declaracion_import` calls `parse_declaracion`, runs the draft through `build_draft`, persists to `AEAT_DRAFTS_DIR`, passes to cluster E's verifier if a ruleset exists, emits the final verdict with warnings.

### 9. Exit criteria per concrete extractor

For a concrete `modelo_N_vY.py` to merge:

1. Passes ≥ 500 parametrised L3 synthetic cases covering edge shapes (zero values, very large, negative carry-forwards).
2. Passes fidelity-validation assertions against ≥ 3 L1/L2 anchors.
3. `Engine.audit_against` via cluster E reports zero discrepancies on all L3 cases.
4. Kent-observable acceptance: `aeat filing import --from-declaracion <anchor_pdf>` produces a draft indistinguishable (modulo `draft_id` / timestamps) from `aeat filing build --inputs <ground_truth>`.

### 10. Out of scope for this cluster

- Modelo 100 (RENTA) — cluster F.
- OCR fallback — tracked as follow-up; MVP assumes text-layer PDFs.
- Modelo 390 extractor body — schema ships via cluster B but the extractor blocks on #221's ruleset.

## Consequences

- `aeat filing import --from-declaracion` becomes Kent's primary calc-verified import path for 130 / 303 / 111 / 115 / 180 / 190.
- Template-revision drift is representable — 2024-09 reshuffles live in their own concrete extractor; old code keeps working for pre-Sept filings.
- Partial extraction is a first-class state — Kent never loses work to a failed parse; he gets "X of Y casillas extracted, review these Z warnings."
- Cluster E's verification pipeline has a clean boundary: it consumes `DeclaracionFiling.values` and produces a verdict; no knowledge of PDF internals.
- Synthetic L3 generator + real L1/L2 anchors + parametrised tests give > 500 cases of coverage per modelo before any PR merges.
- The registry pattern makes adding modelos a matter of adding a single file + its test suite; no core changes.
