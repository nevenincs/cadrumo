---
tags:
  - "#adr"
  - "#real-pdf-import"
date: 2026-04-22
modified: '2026-04-22'
related:
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-22-ruleset-architecture-adr]]"
  - "[[2026-04-22-citation-blocklist-adr]]"
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
---
# aeat-fichero-boe-export-adr

## status

Accepted — 2026-04-22. Wave 75d opens the EPIC #201 execution
thread with this ADR + the `src/aeat/adapters/outbound/aeat/export/_formats/`
module scaffold. Per-modelo schema implementation lands in
wave 76+ research sub-waves. Modelo 130 is the first target.

## context

EPIC #197 (export-first charter) and EPIC #201 (fichero BOE
export) establish that Kent's happy path is:

    produce (ruleset engine) → review (draft lifecycle) → approve
    → export (fichero BOE) → self-upload (AEAT portal "importar datos")

The last three waves of EPIC #305 fixed the *produce* surface
(rulesets + external-anchor tests + citation blocklist at
waves 57b-75c). Every autónomo-core modelo (130/303/390) now has:

- ✅ Schema defined in `src/aeat/domain/formulas/_rulesets/`
- ✅ Formula ruleset with 2024+2025 variants
- ✅ Audit-against-provided tests
- ✅ Filing builder (130 + 303 only)
- ❌ **Fichero BOE serialiser** — this ADR's subject
- ❌ Reference PDF generator
- ❌ CLI wiring

EPIC #201 has 9 children (C3a through C3i). This ADR covers C3a
(schema discovery) + C3b (serialiser implementation) as the
foundational subset. C3c (CLI), C3d (round-trip), C3e (reference
PDF), C3f (Drive upload), C3g (manual portal-compat checklist),
C3h (docs), C3i (approval gate) are separate follow-on scope.

## decision

### 1. Module layout — `src/aeat/adapters/outbound/aeat/export/_formats/`

One Python submodule per modelo-year pairing:

    src/aeat/adapters/outbound/aeat/export/_formats/
        __init__.py            # exports per-modelo serialisers by (modelo, año, template)
        _record_spec.py        # shared Pydantic model for fixed-width field specs
        modelo_130_2024.py     # Q3 2024+ rectificativa-capable schema
        modelo_130_2025.py     # 2025 schema (clone of 2024 unless BOE change)
        modelo_303_2024.py     # Sept 2024+ rectificativa structure
        modelo_303_2025.py
        modelo_390_2024.py
        modelo_390_2025.py
        test_modelo_130_2024.py
        ...

Each concrete module exports:

- `_RECORD_SPECS: tuple[RecordFieldSpec, ...]` — per-field fixed-
  width layout pinned to the BOE *Diseño de registros* version
  (retrieval date + Orden identifier in the module docstring).
- `serialise(draft: FilingDraft) -> bytes` — produces the ASCII /
  ISO-8859-15 byte string Kent uploads.
- `parse(payload: bytes) -> FilingDraft` — the C3d round-trip.

### 2. Fixed-width spec representation

`RecordFieldSpec` is a strict/frozen/extra=forbid Pydantic model:

```python
class RecordFieldSpec(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    offset: int              # 1-based byte offset per BOE convention
    length: int              # byte length
    field_id: str            # AEAT field identifier (e.g. "F01001")
    casilla_id: str | None   # None for header / padding fields
    kind: FieldKind          # ALPHANUMERIC, NUMERIC, DATE, ...
    justification: Justification  # LEFT / RIGHT
    pad_char: str            # " " / "0"
    encoding: Literal["ISO-8859-15"] = "ISO-8859-15"
```

A ruleset-authoring helper `record_field(...)` mirrors the
formulas-ruleset `formula(...)` pattern for concise spec declaration.

### 3. Discovery protocol for the BOE *Diseño de registros*

Each modelo's `_RECORD_SPECS` tuple is hand-authored from the
canonical BOE Orden. The module docstring MUST cite:

- The Orden ministerial identifier and BOE-ID
- The retrieval date of the consolidated text
- A reference to the per-modelo `ModeloMetadata.template_revision`
  (e.g. `"2024.orden-819"` for the Q3 2024+ Modelo 303)

This provenance pattern mirrors the citation-blocklist ADR's
author checklist (wave 67c). Any regression would surface at
the wave 76+ audit loop.

### 4. Encoding + byte-exactness

Fichero BOE files are per-modelo encoded. **Modelo 130** uses
**Windows-1252 / ISO-8859-1** (Orden EHA/672/2007; wave 77b
correction). **Modelo 303 + Modelo 390** use **ISO-8859-1** (Latin-1;
confirmed via AEAT FRECH error docs + DR303e25.xlsx header rows +
DR390e2024.xlsx Nota 3; wave 85b correction — this section
previously claimed ISO-8859-15 as universal, which is wrong). No
currently-shipped autónomo-core modelo uses ISO-8859-15 in the
wire format. Serialiser helpers:

- `encode_currency(value: Decimal, *, length: int) -> bytes`:
  right-justified, zero-padded, no separators, 2 implicit
  decimals. Matches the wave 56 `format_amount` semantics but
  stripped of `.` / `,` and padded.
- `encode_text(value: str, *, length: int, justification: Justification, pad_char: str) -> bytes`:
  left-justified alphanumeric, accent-preserving within ISO-8859-15.
- `encode_date(value: date, fmt: DateFmt) -> bytes`: per-Orden
  date shapes (YYYYMMDD most common; some modelos use DDMMYYYY).

Every encoder returns `bytes` (not `str`) so the caller cannot
accidentally mix encodings.

### 5. Draft-lifecycle gate (C3i dependency)

Not implemented in wave 75d. When C4 (`FilingDraftStatus.APPROVED`)
lands, `aeat.adapters.outbound.aeat.export.export.serialise(draft)` will refuse
unless `draft.status is FilingDraftStatus.APPROVED`. Until then
the serialiser is unguarded — safe because there's no CLI wiring
yet; it's pure library code with no side-effects.

### 6. Test strategy

- `test_modelo_{N}_{year}.py` colocated per module:
  - **Round-trip**: serialise → parse → equality on every casilla.
  - **Byte-exactness**: a golden fixture in
    `tests/fixtures/fichero_boe/` captures a known-good AEAT-
    accepted reference; the serialiser output must match byte-
    for-byte.
  - **Encoding regression**: an ISO-8859-15 spot check using an
    accented character (e.g. NIF letter `Ñ`, label text with
    `í`/`ñ`) to guard against encoder drift.
- **Manual portal-compat** (C3g): out of scope for test
  automation. Record each manual-upload result in
  `.vault/audit/` per the wave 75+ audit cadence.

## implications

### Short-term (wave 76+)

- Ship `_record_spec.py` + module scaffold (wave 75d — this wave).
- Research + populate `modelo_130_2024.py` + `modelo_130_2025.py`
  from the BOE Orden HAC/819/2024 *Diseño de registros* (wave 76).
- Add C3b serialiser + round-trip tests (wave 77).
- Add C3c CLI `aeat submission export` (wave 78).

### Long-term

- 303 + 390 follow the 130 template (waves 79-81).
- 111 / 115 / 123 / 180 / 190 / 347 / 349 fichero BOE variants
  land after the main 3.
- Modelo 100 (IRPF Renta) explicitly deferred per EPIC #201 scope
  ("defer to 0.3.0-beta or 1.0.0").

### Non-goals

- No live submission. The tool produces a file; Kent uploads.
- No automatic encoding detection. ISO-8859-15 is hard-coded.
- No tarifa rendering. Numeric-only fichero BOE fields; the
  trilingual reference PDF (C3e) handles presentation.

## alternatives considered

- **JSON-only export**. Rejected: AEAT portal requires the
  fichero-BOE format for auto-import. JSON can be a secondary
  `--format json` option but does not satisfy the Kent
  end-to-end path.
- **Web-form scraping via Playwright**. Rejected: explicitly
  out of scope per EPIC #197 export-first charter. Kent
  self-uploads via the AEAT portal's "importar datos" UI.
- **Auto-detect the BOE encoding from the Orden's preamble**.
  Rejected as premature optimisation — every autónomo-core
  modelo uses ISO-8859-15 since 2016. If a future modelo
  changes encoding, extend `RecordFieldSpec.encoding` literal.

## references

- Charter: #197 (export-first)
- EPIC: #201 (this ADR's parent)
- `.vault/adr/2026-04-17-export-first-adr.md` — charter-level
  decision that import is always Kent-uploads-file
- `src/aeat/adapters/outbound/aeat/export/_engine.py` — preflight path (pre-export)
- `src/aeat/adapters/outbound/aeat/export/_models.py` — `FilingDraft` shape

## Amendment (2026-05-21): export layouts authored as registry TOML, not Python modules

This ADR's original section 1 described per-modelo Python submodules
under `src/aeat/adapters/outbound/aeat/export/_formats/` as the
authoring surface for `_RECORD_SPECS` tuples derived from the official
AEAT Diseño de Registros. That authoring direction is superseded.

The `calculation-truth-registry` ADR accepted 2026-05-03 established
that export layouts are reviewed registry data, not Python modules.
Under that direction the DR-spec generator (`_generate.py`), its
companion ingestion module (`_ingest.py`), and the DR-spec JSON
fixtures were deleted (commit `97dac2be7`; sanctioned by the
2026-05-21 amendment to the `calculation-truth-registry` ADR).

The decision in this ADR — that Modelo 130 and Modelo 303 fichero-BOE
export support is required — is unchanged. Only the artefact form
changes:

- Export layouts for M130 and M303 are authored as `export_layouts`
  blocks inside the per-modelo registry TOML files
  (`src/aeat/_data/registry/aeat/modelos/130.toml` and
  `src/aeat/_data/registry/aeat/modelos/303.toml`), following the
  pattern already shipped for modelos 180, 202, and 232.
- The generic fixed-width serialiser and deserialiser in
  `src/aeat/adapters/outbound/aeat/export/_formats/` are retained as
  the runtime that consumes registry-authored export layouts at
  execution time; they are not the authoring surface.
- Per-modelo Python format modules (`modelo_130_2024.py` etc.) are
  not created. The Python side owns runtime behaviour; the TOML side
  owns the layout data that must be grounded in the official Diseño.
- Golden round-trip tests derive their expected bytes from the AEAT
  Diseño de Registros corpus, consistent with the no-tautological-
  tests rule and the registry-truth ADR's evidence-grounding mandate.

This amendment is recorded here so that future readers understand why
the Python-module path described in section 1 is absent from the
implementation.
