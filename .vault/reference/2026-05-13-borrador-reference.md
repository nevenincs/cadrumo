---
tags:
  - '#reference'
  - '#borrador'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-borrador-research]]"
---



# `borrador` reference: `borrador package: architectural shape`

Architectural snapshot of `src/aeat/adapters/inbound/borrador/` as of
2026-05-13. The research sibling captures the WHY (design decisions,
detection ladder, regex grammar rationale, registry-profile coverage
gate); this reference captures the WHAT — the current module layout,
the stable public-API surface, the internal pipeline composition,
the pydantic schema field shapes, the error hierarchy, and the PDF
backend abstraction. Final acceptance-criterion closure for audit
gap #506.

## Module layout

The package decomposes into one public surface + five private
modules:

- `__init__.py` — public surface. Re-exports `parse_borrador` and
  the five schema / error / mode types. Imports nothing from
  `_extractors/` or `_parsers/` directly so consumers never see
  the internal pipeline.

- `_parser.py` — composes the detector + per-año extractor
  dispatcher behind the single-function `parse_borrador` entry
  point.

- `_detect.py` — artefact-kind detection. Reads the PDF text via
  the parsers backend and returns the matching `ArtefactKind`
  member, raising `ArtefactNotRecognisedError` when no marker
  matches.

- `_schema.py` — pydantic v2 record definitions. Holds
  `ArtefactKind`, `BorradorParseMode`, `BorradorExtractionProfile`
  (Protocol), and `BorradorObservation`.

- `_errors.py` — error hierarchy. `BorradorParseError` extends
  `PdfFilingImportError` (the shared inbound-PDF base); the
  detection helper raises `ArtefactNotRecognisedError` as a
  subclass.

- `_extractors/` — per-año extractor registry. Holds
  `_REGISTRY_BY_AÑO`, `get_extractor`, and the concrete
  `Modelo100ObservedV2025Extractor`.

- `_parsers/` — PDF backend abstraction. The single seam where
  the upstream `pdfplumber` dependency lives; surfaces
  `extract_pages_text(pdf_path) -> tuple[str, ...]` to the rest
  of the package.

## Public API surface

The package's `__all__` declares six names:

| name | kind | contract |
|------|------|----------|
| `parse_borrador` | callable | `(pdf_path, *, artefact_kind_override=None, año_override=None, extraction_profile=None, parse_mode=OBSERVED) -> BorradorObservation` |
| `BorradorObservation` | pydantic record | strict / frozen / extra="forbid"; carries `modelo`, `ejercicio`, `tax_id`, `artefact_kind`, `values`, optional registry-profile fields, source provenance trio, parsed-at timestamp, optional CSV, warnings |
| `BorradorParseMode` | StrEnum | `OBSERVED` (default — no minimum coverage) vs `REGISTRY_PROFILE` (requires profile, enforces coverage) |
| `BorradorExtractionProfile` | Protocol | `id: str`, `target_casillas: tuple[str, ...]`, `min_coverage: Decimal` — the surface the parser consumes from a registry extraction profile |
| `ArtefactKind` | StrEnum | `BORRADOR` / `PREDECLARACION` / `DECLARACION` |
| `BorradorParseError` | exception | base class; subclassed by `ArtefactNotRecognisedError` (raised on detection failure) and raised directly on every other parse failure |

The public surface is intentionally narrow. Consumers do not see
the per-año extractor classes, the PDF backend, the casilla-row
regex grammar, or the detection regex set. Adding a new public
name requires explicit `__all__` extension.

## Internal pipeline

`parse_borrador` composes the package in a strict three-step
pipeline:

1. **Artefact-kind detection** —
   `detect_artefact_kind(path)` when no override is supplied. Reads
   pages via `extract_pages_text`, joins them, runs the precedence
   ladder (`VISTA PREVIA` → `Código Seguro de Verificación` →
   `BORRADOR`), and returns the matching `ArtefactKind`. Raises
   `ArtefactNotRecognisedError` when nothing matches.

2. **Per-año dispatch** — `get_extractor(año)` consults the
   `_REGISTRY_BY_AÑO: dict[int, type]` lookup with the supplied
   `año_override` or the default 2025. Returns a fresh instance
   of the matching extractor class. Raises `BorradorParseError`
   listing the supported años when the requested one is absent.

3. **Extraction** — `extractor.extract(pdf_path, artefact_kind,
   extraction_profile=...)`. The 2025 extractor re-reads the page
   text (the detector's read is not threaded through — a
   deliberate choice to keep each step independently invokable),
   pulls the required header anchors (`NIF`, `Ejercicio`,
   optional `CSV`), walks the multiline casilla-row regex, and
   builds the strict `BorradorObservation`. When a registry
   extraction profile is supplied, the extractor filters to its
   target casillas, computes `coverage = matched / declared`, and
   raises if `coverage < profile.min_coverage`.

Each step has a single explicit failure mode (typed exception)
and a single happy-path output. The pipeline is linear; no step
mutates global state.

## Schema surface

All four pydantic records share the `_STRICT_FROZEN` config
(`strict=True, frozen=True, extra="forbid"`).

### `ArtefactKind` (StrEnum)

- `BORRADOR = "BORRADOR"` — pre-filing draft from Portal Renta.
- `PREDECLARACION = "PREDECLARACION"` — simulation watermarked
  `VISTA PREVIA`.
- `DECLARACION = "DECLARACION"` — post-filing copy with CSV stamp.

### `BorradorParseMode` (StrEnum)

- `OBSERVED = "observed"` — default mode; returns observed rows
  without minimum-coverage enforcement.
- `REGISTRY_PROFILE = "registry_profile"` — requires
  `extraction_profile`; coverage below profile minimum raises.

### `BorradorExtractionProfile` (Protocol)

- `id: str` — profile identifier (registry-supplied).
- `target_casillas: tuple[str, ...]` — declared target casilla ids.
- `min_coverage: Decimal` — minimum acceptable coverage ratio.

### `BorradorObservation` (pydantic v2 record)

- `modelo: Literal["100"]` — fixed at the modelo level.
- `ejercicio: str` (4 chars) — four-digit tax year extracted from
  the PDF header.
- `tax_id: str` (4–32 chars) — NIF / NIE extracted from the
  header, uppercased.
- `artefact_kind: ArtefactKind` — discovered artefact kind.
- `values: tuple[ExtractedCasilla, ...]` — observed casilla rows
  (the shared `ExtractedCasilla` shape comes from the
  inbound-pdf package: `casilla_id`, `printed_value`,
  `source_page`, optional `source_bbox`,
  `extraction_confidence`).
- `registry_extraction_profile_id: str | None` — profile id when
  registry-profile parsing was used; otherwise `None`.
- `extraction_coverage: Decimal | None` — observed coverage when
  a profile was supplied; otherwise `None`.
- `source_pdf_path: Path` — resolved absolute path.
- `source_pdf_sha256: str` (64-hex pattern) — lowercase hex
  SHA-256 of source bytes; provenance gate against local
  filesystem swaps.
- `parsed_at: datetime` — UTC timestamp at parse completion.
- `csv: str | None` — AEAT `Código Seguro de Verificación` when
  the artefact is a `DECLARACION`; `None` otherwise.
- `warnings: tuple[str, ...]` — per-casilla advisory messages
  (e.g., unparseable amount) that did not prevent parse
  completion.

## Error hierarchy

The package's error tree:

- `aeat.adapters.inbound.pdf._errors.PdfFilingImportError` —
  upstream base for every inbound-PDF failure.
- `BorradorParseError(PdfFilingImportError)` — base for Modelo
  100 specific failures. Raised directly when:
  - Registry-profile mode is requested without a profile.
  - A `DECLARACION` artefact lacks a CSV stamp.
  - The registered extractor for the requested `año` does not
    exist.
  - Registry-profile coverage falls below `min_coverage`.
  - Required header field (`NIF` or `ejercicio`) cannot be
    located in the PDF text.
- `ArtefactNotRecognisedError(BorradorParseError)` — raised by
  `detect_artefact_kind` when no marker matches.

Every consumer catches `BorradorParseError` to handle the broad
failure mode; specialised consumers may catch
`ArtefactNotRecognisedError` to surface a more actionable error
to the operator.

## PDF backend abstraction

`_parsers/__init__.py` re-exports `extract_pages_text` from
`_parsers/_pdfplumber_backend.py`. The backend module is the
single seam where the upstream `pdfplumber` dependency lives —
every other module in the package consumes the
`tuple[str, ...]` page-text output without seeing pdfplumber's
own types.

This shape lets a future second PDF backend (e.g.,
pypdfium2-based for layout-aware extraction) drop in alongside
`_pdfplumber_backend.py` and be selected via a config switch or
backend-detection probe without touching the detector or
extractor code paths.

## Test-coverage surface

The single test module
`adapters/inbound/borrador/test_modelo_100_summary.py` pins the
parser's contract assertions. The research sibling enumerates the
seven categories (happy-path borrador, predeclaración detection,
declaración detection, declaración-without-CSV raise,
unrecognised-artefact raise, registry-profile happy path,
registry-profile coverage failure).

## Stability surface

Names and shapes covered by the public-API stability contract
(MUST NOT change without a paired ADR):

- The six `__all__` exports.
- `parse_borrador`'s kwarg names and types.
- `BorradorObservation`'s field set and per-field type
  annotations.
- The error hierarchy's class names and inheritance shape.

Internal implementation surfaces (free to evolve under the
public contract): the casilla-row regex, the header-anchor
regexes, the `_REGISTRY_BY_AÑO` keys, the `extract_pages_text`
backend, the per-año extractor's internal helper functions
(`_observed_values`, `_require_match`, `_sha256_file`).
