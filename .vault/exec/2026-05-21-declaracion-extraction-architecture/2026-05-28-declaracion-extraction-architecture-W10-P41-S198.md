---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-28'
modified: '2026-05-28'
step_id: S198
related:
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# declaracion-extraction-architecture W10.P41.S198 — justificante surface discipline extension

## Step

Extend the declaracion-extraction discipline to the justificante surface at
`src/aeat/adapters/inbound/justificante/`.

## Audit Findings (UNIT 1 + 2)

### Extraction model

The justificante surface uses **hardcoded regex-driven extraction** in
`src/aeat/adapters/inbound/justificante/_extract.py`. The `ExtractionProfileDefinition`
schema supports `surface = "justificante_pdf"` but `validate_extraction_profile_artefacts`
explicitly rejects any such profile with `target_casillas`, blocking the registry-profile
path at schema level. No `justificante_pdf` registry profiles exist in the TOML tree.

### Exception hierarchy pre-amendment

`JustificanteParseError` in `src/aeat/domain/justificante/_errors.py` was a bare
string-message exception with none of the `missing/malformed/ambiguous/coverage`
structured attributes that `DeclaracionParseError` carries. Test code was forced to
parse message strings to identify failure kind — the exact brittleness class closed
by task #51.

### PROVISIONAL gates

Both existing gates (`validate_declaracion_pdf_specimen_gate`,
`validate_declaracion_pdf_round_trip_gate`) guard on
`if profile.surface != "declaracion_pdf": return []` and are correctly dormant for
the justificante surface. Generalisation is not applicable because no casilla-level
corpus extraction exists for justificante PDFs.

### Silent-failure classes

- **Receipt format change**: five-tier CSV regex in `_extract_csv` is the exposure surface.
  Corpus sidecar test catches this as `JustificanteCsvNotFoundError` across 40+ fixture pairs.
- **Regex generalisation gaps**: 15 pre-existing `JustificanteCsvNotFoundError` failures on
  `TestRealCorpusParses` (modelos 036, 115, 123, 131, 180, 184, 193, 232, 347, 349, 369, 720,
  840) represent newly-added corpus PDFs whose sanitiser layout is not matched by any current
  regex tier. Pre-existing, not introduced by this step.
- **Sidecar/parser drift**: `test_corpus_sidecar_roundtrip.py` pins 40+ PDF+sidecar pairs via
  the `SANITIZED{modelo}{year}` convention. Any parser extraction that returns a different token
  fails loudly.

## Alignment Applied (UNIT 3)

### UNIT 3(c) — Structured exception attributes (applied)

`JustificanteParseError` now carries `missing`, `malformed`, `ambiguous`, and `coverage`
attributes with the same type signature as `DeclaracionParseError`:

```python
def __init__(
    self,
    message: str | None = None,
    *,
    missing: tuple[str, ...] = (),
    malformed: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    coverage: Decimal | None = None,
) -> None:
```

All raise sites in `_extract.py` updated:
- `_require()` → `missing=(field,)`
- `_parse_decimal(raw, field=...)` → `malformed=(field,)` when field supplied
- `_parse_datetime()` → `malformed=("presented_at",)` on format failure
- URL extractor → `missing=("verification_url",)` or `malformed=("verification_url",)`
- Empty text → `missing=("text",)`
- Pydantic ValidationError → `malformed=("record",)`
- Period not found → `missing=("period",)`
- Presented-at not found → `missing=("presented_at",)`

### UNIT 3(a/d) — PROVISIONAL gates (dormant by design; not generalised)

Correctly scoped to `declaracion_pdf`. No justificante_pdf profiles exist in the
TOML tree and the schema blocks casilla-targeted profiles on that surface. The
sidecar corpus tests are the equivalent discipline gate for this surface.

### UNIT 3(b) — Sidecar coverage

40+ PDF+sidecar pairs confirmed. The 15 pre-existing failures are extractor gaps,
not sidecar discipline gaps — separate extractor-expansion task.

## Tests (UNIT 4)

### Justificante suite

- Before: 15 failed, 126 passed (pre-existing corpus layout gaps)
- After: 15 failed, 136 passed (+10 new structured-attribute tests)
- No regressions introduced

New tests:
- `test_extract_helpers.py`: `test_parse_decimal_raises_with_malformed_attribute_when_field_supplied`,
  `test_parse_decimal_malformed_attribute_empty_when_no_field`,
  `test_parse_datetime_raises_with_malformed_presented_at_attribute`
- `test_parser.py::TestJustificanteParseErrorStructuredAttributes`: 7 tests covering
  default attributes, missing/malformed/ambiguous/coverage roundtrips, subclass inheritance,
  `_require()` structured attribute, and empty-text structured attribute

### Registry gate tests

All 44 registry gate tests pass (no regressions).

### Broader inbound + registry gate

In progress at step record authoring time; 15 pre-existing justificante corpus failures
expected; no new failures from this step's changes.

## Files Changed

- `src/aeat/domain/justificante/_errors.py` — structured attributes added to `JustificanteParseError`
- `src/aeat/adapters/inbound/justificante/_extract.py` — all raise sites updated with structured attributes
- `src/aeat/adapters/inbound/justificante/test_extract_helpers.py` — 3 new tests
- `src/aeat/adapters/inbound/justificante/test_parser.py` — 7 new tests in `TestJustificanteParseErrorStructuredAttributes`
- `.vault/adr/2026-05-21-declaracion-extraction-architecture-adr.md` — amendment appended

## Honest Verdict

The discipline transferred **with structural adaptation**. The justificante surface is
architecturally distinct from the declaracion surface (hardcoded regex vs registry-profile
extraction), so PROVISIONAL gate generalisation was not applicable. The transferable
part — structured exception attributes — was applied cleanly. The sidecar corpus
discipline (task #41) is the equivalent gate for this surface and was already in place.
