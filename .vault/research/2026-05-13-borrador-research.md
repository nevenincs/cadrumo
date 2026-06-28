---
tags:
  - '#research'
  - '#borrador'
date: '2026-05-13'
modified: '2026-05-13'
related: []
---



# `borrador` research: `Modelo 100 PDF parsing: borrador / predeclaración / declaración layout-discovery`

Backfill captured to satisfy the second remaining acceptance
criterion of audit gap #506 — the borrador parser ships in
production with no `.vault/` research trail. This document captures
the three Modelo 100 PDF artefact kinds the parser handles, the
detection ladder, the per-año extractor registry pattern, the
casilla-row regex grammar, the registry-extraction-profile coverage
gate, and the source-of-truth provenance hash carried on every
observation.

## Findings

### Domain purpose

Modelo 100 (IRPF / Renta) ships in three PDF artefact shapes a
Spanish autónomo encounters at different points in the filing
lifecycle:

- **Borrador** — the pre-filing draft AEAT generates from data it
  already holds (employment retenciones, financial-income
  retentions, capital gains, etc.). Downloaded from the Portal
  Renta. Carries pre-populated casillas but NO CSV (it is not a
  filing).
- **Predeclaración / simulación** — a non-binding simulation
  generated from Renta Web Open. Same structural shape as the
  borrador but watermarked `VISTA PREVIA`. Used by the operator
  (or the project's parity oracle) to verify a payload before
  filing.
- **Declaración** — the post-filing copy AEAT returns after a
  successful submission. Same shape but stamped with an AEAT
  `Código Seguro de Verificación` (CSV).

The parser's purpose is to extract every printed casilla/value
row from any of the three artefacts. Completeness is enforced
only when the caller passes a registry extraction profile; the
default `OBSERVED` parse mode returns whatever the PDF prints
without minimum-coverage requirements.

### Artefact-kind detection ladder

The three markers carry different evidentiary weights:

1. **`VISTA PREVIA`** watermark — strongest signal of non-binding
   status. If present, the artefact is a `PREDECLARACION` even
   when other markers are also visible (for example, a
   predeclaración generated from an existing draft can carry the
   `BORRADOR` header in passing).

2. **CSV stamp** (`Código Seguro de Verificación` or its `Codigo
   Seguro de Verificacion` ascii-stripped form) — proof that AEAT
   accepted the filing. A filed `DECLARACION` always carries a
   CSV. Trumps the `BORRADOR` header because a filed declaración's
   archived copy can retain the original `BORRADOR` text in
   non-prominent sections.

3. **`BORRADOR`** header — the weakest signal because it appears
   on every variant (the AEAT-side templating reuses the same
   layout for borrador and declaración alike; only the watermark
   or CSV stamp differs).

The detector enforces this precedence ladder explicitly. When
none of the three markers match, it raises
`ArtefactNotRecognisedError` with a diagnostic listing the
expected markers — the caller is allowed to bypass detection via
the `artefact_kind_override` kwarg on `parse_borrador` for tests
or for forensic replays of malformed PDFs.

### Per-año extractor registry

Modelo 100 layouts evolve year-over-year. AEAT historically
publishes a new dr.xls each ejercicio with slightly different
column anchors, header titles, and casilla numbering. The parser
dispatches to a per-año extractor via the
`_REGISTRY_BY_AÑO: dict[int, type]` lookup in
`_extractors/__init__.py`. The single registered extractor today
is `Modelo100ObservedV2025Extractor` (`año=2025`).

The dispatcher is intentionally strict: passing an unsupported
`año` raises `BorradorParseError` listing the supported set. There
is no "best-effort fallback to last-known year" — silently
matching a 2024 borrador with a 2025 extractor would corrupt the
observed values without any warning.

Future ejercicios are added by:

1. Authoring `modelo_100_summary_v{año}.py` with a class
   exposing the same `extract(pdf_path, artefact_kind,
   extraction_profile=None) -> BorradorObservation` contract.
2. Registering the class under the matching `año` key in
   `_REGISTRY_BY_AÑO`.

No central per-año adapter Protocol is enforced today because
only one año extractor exists; when a second lands, a Protocol
class should be added to `_schema.py` and both extractors should
declare conformance.

### Casilla-row regex grammar

The 2025 extractor's row regex is the project's load-bearing
PDF-to-data primitive:

```
(?m)^\s*(?P<casilla_id>[0-9]{4})\s[^\n]{0,160}?{SPANISH_AMOUNT_GROUP}
```

Key invariants:

- `(?m)` — multiline mode so `^` matches each line, not just the
  first character of the page text.
- `(?P<casilla_id>[0-9]{4})` — exactly four digits at line start.
  Modelo 100 casillas are zero-padded to four digits (`0505`,
  `0521`, etc.). Three-digit casillas appear in some printouts
  but not as primary anchors.
- `[^\n]{0,160}?` — the label between the casilla id and the
  printed amount can be up to 160 characters (the longest
  observed labels are the autonomic-scale per-CCAA names which
  approach this bound). The lazy quantifier `?` forces the regex
  to stop at the first amount-shaped sub-string.
- `SPANISH_AMOUNT_GROUP` — imported from
  `adapters/inbound/pdf/_label_regex` and shared with the
  justificante / declaración parsers. Matches Spanish-locale
  amounts (`1.234,56` with comma decimal + dot thousands
  separator, optional negative sign, optional EUR suffix). The
  shared grammar guarantees that label-vs-amount disambiguation
  matches the same wire format across every Modelo 100 PDF
  variant.

The header anchors `_NIF_RE`, `_EJERCICIO_RE`, and `_CSV_RE` are
required-match (raise on absence) for `NIF` and `ejercicio`, and
required-for-DECLARACION-only for the CSV stamp. A `BORRADOR` or
`PREDECLARACION` artefact without a CSV is intentionally allowed.

### Registry-extraction-profile coverage gate

When the caller passes an `extraction_profile`, the extractor
filters observed casillas to the profile's `target_casillas` set
and computes `coverage = matched / declared`. The parse fails
hard if `coverage < profile.min_coverage`, listing the missing
casilla ids in the raised `BorradorParseError`. This gate is the
guardrail against silently degrading parse quality across PDF
template changes — if AEAT renames or relocates a casilla and
the regex no longer matches it, the coverage drops below the
profile's minimum and downstream consumers (filing draft
build) get a hard failure instead of a partially-populated
record.

The coverage value is preserved on the returned
`BorradorObservation.extraction_coverage` so consumers can
distinguish "100% profile coverage" from "profile coverage at
the minimum threshold".

### Source-of-truth provenance

Every `BorradorObservation` carries:

- `source_pdf_path: Path` — the resolved absolute path of the
  parsed PDF.
- `source_pdf_sha256: str` — the lowercase hex SHA-256 of the
  source bytes. Computed at parse time and stored on the
  observation so downstream consumers can re-verify the source
  without trusting the path.
- `parsed_at: datetime` — UTC timestamp at parse completion.

This trio is the parser's provenance-trail contract: a
downstream consumer (filing draft assembly, reconciliation
report) can cite "this draft was assembled from PDF X at hash Y
at time Z" without needing access to the original bytes. The
SHA-256 in particular protects against a "the borrador we just
parsed has been swapped for a different one" attack on the
local filesystem.

### Cross-package consumers

`parse_borrador` is currently consumed only by tests
(`test_modelo_100_summary.py`). The CLI import flow and the
justificante reconciliation surface use it via the public
`aeat.adapters.inbound.borrador` package surface. The thin
re-export discipline (only `parse_borrador` + the four schema
types in `__all__`) lets consumers depend on the public API
without reaching into `_extractors/` or `_parsers/`.

### Test-coverage trail

The single test module `test_modelo_100_summary.py` carries the
parser's contract assertions:

- Happy-path borrador parse: a fixture PDF (or a constructed
  fixture text) → observation with non-empty `values`,
  `artefact_kind=BORRADOR`, `csv=None`.
- Predeclaración detection: VISTA PREVIA watermark routes to
  `ArtefactKind.PREDECLARACION` even with a CSV elsewhere in
  the text.
- Declaración detection: CSV stamp routes to
  `ArtefactKind.DECLARACION`.
- DECLARACION-without-CSV raises `BorradorParseError`.
- Unrecognised artefact raises `ArtefactNotRecognisedError`.
- Registry-extraction-profile happy path: coverage at or above
  minimum yields a populated observation.
- Registry-extraction-profile failure: coverage below minimum
  raises `BorradorParseError` listing missing casillas.

### Boundary cases / known limitations

- **Three-digit casilla numbers in some printouts**: the regex
  requires exactly four digits at line start. Modelo 100's
  primary casillas are zero-padded to four digits so this is
  the correct shape; three-digit informal references (in label
  prose) are intentionally NOT matched as anchors.
- **Page-break header repetition**: the extractor joins page
  text with `"\n"` and runs the regex over the combined string.
  Header text that repeats on every page (the AEAT page banner)
  produces redundant `NIF`/`Ejercicio` matches, all of which the
  detector tolerates — only the first is consumed via
  `_NIF_RE.search`.
- **Mixed-case headers**: every header regex carries
  `re.IGNORECASE` so AEAT layout-version variants ("Ejercicio:"
  vs "EJERCICIO :" vs "ejercicio") all match.
- **Amount-with-EUR-suffix vs amount-bare**: the shared
  `SPANISH_AMOUNT_GROUP` accepts both forms. The extractor
  preserves the parsed `Decimal` without the suffix; downstream
  consumers see the canonical numeric form regardless of the
  PDF's printed-amount convention.

### Open questions / future work

- **Multi-año extractor surface**: when a second año extractor
  lands (e.g., 2024 for retrospective filings), formalise the
  `BorradorExtractor` Protocol in `_schema.py` and have the
  registry dispatch via the Protocol contract instead of the
  bare `type` annotation.
- **Bounding-box capture for `ExtractedCasilla.source_bbox`**:
  the current extractor sets `source_bbox=None` because the
  pdfplumber backend reports text-extraction results without
  the layout coordinates that would let consumers replay the
  parse on a different PDF. Future work could thread the
  per-row bbox through if a consumer needs it.
- **OCR fallback for scanned PDFs**: AEAT borrador PDFs are
  text-layer-native, but a scanned variant produced by older
  Portal Renta exports could surface in field. The current
  parser would raise on empty extracted text. An OCR fallback
  is intentionally out of scope (would inflate the dependency
  tree and risks silently corrupting numeric values).
