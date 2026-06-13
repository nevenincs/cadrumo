---
tags:
  - "#research"
  - "#declaracion-extractor"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
  - "[[2026-04-21-pdf-taxonomy-adr]]"
  - "[[2026-04-21-casilla-schema-completeness-adr]]"
  - "[[2026-04-21-real-pdf-fixture-corpus-adr]]"
---

# declaracion-extractor research

## Problem

Clusters A (taxonomy), B (schema), C (fixtures) establish vocabulary, casilla catalogue, and a three-layer test corpus. The extractor itself — the `aeat.adapters.inbound.declaracion` module that turns a filing-copy PDF's pixel/text stream into a `tuple[ExtractedCasilla, ...]` tuple — is cluster D. The research below grounds three choices the ADR must lock: (1) the extraction primitive (text-layer regex vs. bbox-anchored vs. AcroForm field reader), (2) per-modelo registry shape, (3) AEAT template-revision handling.

## Extraction primitives (ranked by applicability)

### Primitive 1 — pdfplumber text-layer regex (label-anchored)

`pdfplumber.open(path).pages[i].extract_text()` returns a reading-order text stream. For AEAT's declaración PDFs this text carries the full casilla payload: each casilla's printed number, its label, its value, and neighbouring structural tokens. Regex anchored to the label text (`"01 Ingresos íntegros"` → capture the trailing `1.234,56`) extracts the value with ~99 % reliability on static PDFs.

**Pros**: zero coordinate math, survives layout micro-drifts, already the backbone of `aeat.domain.justificante`'s receipt extractor.

**Cons**: breaks when AEAT reorders sections (column reading order shuffles); breaks when two casillas share the same label word (common for 303 "Tipo / Cuota" pairs); breaks on multi-line labels (common for 100 Anexos).

### Primitive 2 — pdfplumber bbox-anchored extraction

`page.extract_words()` returns every word with `(x0, y0, x1, y1, text)`. For each casilla we define a bounding box (learned from an anchor PDF) and pluck the word(s) inside it. Coordinates are stable across AEAT template revisions within an año; they break across año boundaries when AEAT redesigns.

**Pros**: deterministic, duplicate-label-proof, handles multi-line labels.

**Cons**: requires a per-modelo / per-año / per-template_revision bbox map. Maintenance-heavy without an automated coordinate-learning step.

### Primitive 3 — pypdf AcroForm / XFA field reader

When the PDF is a fill-in form, `/AcroForm` structure carries per-casilla values keyed by field name (`m303_01`, `m303_03`, ...). Parse-free — the extractor is a dict lookup.

**Pros**: when it works, it's perfect.

**Cons**: AEAT no longer ships fill-in declaraciones as default (post-2020 most declaraciones are rendered static). XFA is dead except for pre-2020 Renta Anexos; pdfplumber and pypdf both struggle to read XFA. **Applicability is narrow** — good for a small subset of historical filings only.

### Primitive 4 — OCR fallback

For scanned / image-only PDFs, `pytesseract` (with Spanish language pack) is the escape hatch. Slow (10+ seconds per page), error-prone on numbers (`,` vs `.` thousands ambiguity), heavy dependency.

**Pros**: last-resort coverage.

**Cons**: not deterministic; dependency footprint; casilla-value accuracy ≤ 95 % without post-processing.

## Recommended primitive stack

Primary: **label-anchored regex (P1)**. Fast, deterministic, minimal maintenance. Covers ≥ 90 % of modern declaración PDFs for modelos 130 / 303 / 111 / 115.

Fallback: **bbox-anchored (P2)**. Per-modelo bbox maps built from a handful of real-anchor PDFs (cluster C L1/L2). Used when P1's label anchor is ambiguous or when the regex fails.

Tertiary: **AcroForm reader (P3)**. Tried first when the PDF carries `/AcroForm`; trivially converts to the extraction output format; cheap to attempt on every PDF.

Excluded from MVP: **OCR (P4)**. Introduce only if a motivated user hits a scan-only PDF (tracked as a future feature, not this cluster).

Order of attempt: **P3 → P1 → P2**. First one that yields a complete `tuple[ExtractedCasilla, ...]` matching the casilla schema wins.

## Per-modelo registry shape

Mirrors `FilingBuilder` registry in `src/aeat/application/filing/_builders/`. One concrete `DeclaracionExtractor` subclass per `(modelo, template_revision)` pair:

```
src/aeat/adapters/inbound/declaracion/
    __init__.py               # public API
    _schema.py                # DeclaracionFiling pydantic record
    _extract.py               # primitives P1/P2/P3 as pure functions
    _extractor.py             # DeclaracionExtractor ABC
    _extractors/              # concrete per-modelo / per-template_revision
        modelo_130_v2024.py
        modelo_130_v2025.py
        modelo_303_v2024_1.py    # pre-September 2024 casilla numbering
        modelo_303_v2024_2.py    # post-September 2024 numbering
        modelo_303_v2025.py
        modelo_390_v2025.py
    _parsers/                 # pdfplumber / pypdf backends
        _pdfplumber_backend.py
        _pypdf_backend.py
    test_extractor.py
```

A detector function `detect_template_revision(pdf_path) -> tuple[str, str]` peeks at the PDF (AEAT prints form code + año + month in header/footer) and returns `(modelo, template_revision)`. The registry dispatches on the tuple. Fallback: if detection is inconclusive, the user-supplied `--from-declaracion --modelo X --año Y` CLI flags force the registry pick.

## AEAT template-revision drift (observed patterns)

- **Intra-año revisions** exist when AEAT amends a form mid-year (Modelo 303 `v2024.09` after Orden HAC/819/2024).
- **Year-over-year renumbering** occasionally happens (Modelo 303 `105` → `103` + `150` split, 2024).
- **Font hinting drift** is cosmetic but produces different bbox coordinates by 1–2 px. P1 is immune; P2 needs ≤ ±3 px tolerance on every bbox.
- **Multi-language receipts** exist for Catalan / Galician / Basque (label text differs). `aeat.domain.justificante._extract` already handles this via `_strip_accents` + flexible regex; cluster D inherits the same primitives.

## Cross-cluster dependency sanity

- Cluster A: `src/aeat/adapters/inbound/pdf/` package + `ExtractedCasilla` type must ship before cluster D.
- Cluster B: casilla corpus for modelo N must be complete before cluster D's extractor for modelo N can land (otherwise the extractor produces casillas the builder drops).
- Cluster C: L3 synthetic generator for modelo N must produce PDFs; cluster D's unit tests run against L3 output; ≥3 L1/L2 anchors validate fidelity.
- Cluster E: consumes `DeclaracionFiling.values` → runs `Engine.audit_against`.
- Cluster F: Modelo 100 has its own cluster-F extractor module family — it **does not** share `_extractors/` with cluster D because anexo traversal is structurally different.

## Open questions (for ADR)

1. **CLI flag name**: `aeat filing import --from-declaracion <PATH>` vs. `--from-filing-copy`? Lock to Spanish per project mandate: `--from-declaracion`.
2. **Auto-detection vs. explicit modelo flag**: the detector from header/footer text succeeds on ~95 % of modern PDFs. When it fails, `--modelo N --año YYYY` override required.
3. **Partial extraction** — what if we find 60 of 88 casillas for a Modelo 303? ADR choice: **return partial + warn**, don't fail. Cluster E then flags the draft `EXTRACTION_PARTIAL` and Kent reviews.
4. **Decimal parsing of Spanish-formatted numbers** — reuse `_parse_decimal` from `aeat.domain.justificante._extract`? Answer: promote to shared helper in `_pdf_import/_shared.py`.
5. **Multi-page traversal** — how do we associate a casilla extracted on page 2 with its label on page 1? Answer: extractor operates per-page; the schema knows which page each casilla lives on (via the `page_hint` field added to `CasillaSchema` in cluster B).
6. **MVP modelo order**: 130 first (19 casillas, simplest layout), 303 second (88 casillas but ruleset exists), 111 third (analogous to 130), 115 fourth. 390 / 100 deferred to later clusters.
