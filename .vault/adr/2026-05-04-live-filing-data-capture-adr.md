---
tags:
  - '#adr'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-04-live-filing-data-capture-research]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
---



# `calculation-truth-registry` adr: `Live filed-declaration data capture` | (**status:** `accepted`)

## Problem Statement

The calculation registry requires previous-filing facts and live AEAT
cross-reference evidence. The existing live-read implementation can authenticate
with Cl@ve Movil, query AEAT's filed-declarations register, and capture
justificante PDFs, but it does not yet capture the full filed-declaration data
that contains the modelo's casillas.

That gap is architecturally unsafe. A justificante proves presentation metadata,
CSV identity, timestamp, and totals, but it is not a sufficient source for
registry bindings such as previous-year economic-activity net income or
previous-period casilla values. A live reader that cannot capture and normalize
full filed-declaration artefacts cannot support production-grade previous-filing
bindings.

## Considerations

AEAT's filed-declarations query exposes multiple artefacts for a filed return:
register metadata, justificante, copy of the declaration, and submitted-file
download. The submitted file is the preferred machine-readable source where
available. The full declaration PDF is a required evidence and fallback source
because the filed modelo PDF carries casillas. The justificante remains
provenance evidence rather than full calculation data.

The codebase already has several necessary pieces:

- `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` authenticates via
  Cl@ve Movil and stores a session state.
- `src/aeat/adapters/outbound/aeat/sede/_declarations.py` queries
  `Consultar declaraciones presentadas` and captures justificante PDFs.
- `src/aeat/adapters/outbound/aeat/sede/_walker.py` captures justificantes
  through `Mis Expedientes` as a second read path.
- `src/aeat/adapters/inbound/justificante/_parser.py` parses receipt metadata.
- `src/aeat/adapters/inbound/declaracion/_parser.py` detects declaration
  templates but intentionally refuses because registry-backed extraction is not
  implemented.
- `src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py`
  proves PDF casilla extraction is possible, but only for a narrow Modelo 100
  summary surface.

## Constraints

Live AEAT reads are legally sensitive and must remain read-only. The backend
must not perform AEAT writes, remote saves, presentation, signing, payment,
direct debit, amendment, cancellation, or document submission. It must also not
use authenticated AEAT filing portals as synthetic calculation engines.

Parsed live artefacts are observations. They do not become legal truth and do
not define supported modelos, casillas, formulas, revisions, or calculation
coverage. Registry snapshots define what observations mean.

The normalized live-read output must preserve provenance: retrieval surface,
source URL, artefact kind, content hash, retrieval timestamp, authenticated
identity, modelo, ejercicio, period, expediente, CSV, and parser coverage.

## Implementation

Add a live filing-data capture backend before concrete modelo implementation.
The backend must extend the existing declaration-register reader so one
read-only query can capture every available artefact for a filed declaration:

1. Filed-register row metadata from `Consultar declaraciones presentadas`.
2. Submitted TXT or model-specific file where AEAT exposes one.
3. Full declaration-copy PDF where AEAT exposes one.
4. Justificante PDF.
5. Source URLs, byte counts, SHA-256 hashes, retrieval timestamps, and parser
   coverage details for each artefact.

Introduce a normalized observation schema:

```text
FiledDeclarationObservation
  modelo: ModeloId
  ejercicio: int
  period: str
  expediente_id: str
  status: str
  presented_at: datetime
  authenticated_identity: str
  artefacts: list[FiledDeclarationArtefact]
  casillas: list[ObservedCasillaValue]
  metadata: dict[str, scalar]
  extraction_coverage: ExtractionCoverage
  registry_snapshot_id: str | null
```

```text
FiledDeclarationArtefact
  kind: register_row | submitted_file | declaration_pdf | justificante_pdf
  source_url: str
  content_type: str | null
  byte_count: int
  sha256: str
  captured_at: datetime
```

```text
ObservedCasillaValue
  casilla_id: CasillaId
  value: Decimal | str | bool | null
  source_artefact_kind: submitted_file | declaration_pdf
  source_locator: str
  confidence: Decimal
```

The submitted file parser is the preferred path. It must use registry export
layouts and extraction profiles to map fields into casilla observations. The
declaration PDF parser is the fallback path and must use registry extraction
profiles for labels, bounding boxes, form fields, or other extraction
primitives. The justificante parser remains a metadata/provenance parser.

Registry validation must require every live extraction profile to declare
target casillas, required coverage, accepted artefact kinds, source evidence,
and failure semantics. A missing or incomplete extraction profile fails hard
when a live-read result is requested for filing-grade use.

## Rationale

This keeps the accepted central registry architecture intact. AEAT live data is
not a second authority; it is an observed-data provider whose output is
interpreted by validated registry snapshots.

Submitted files are preferred because they are closer to the filed data model
than human-readable PDFs. PDFs remain mandatory evidence because filed modelo
copies contain casillas and because AEAT may not expose the submitted file for
every modelo or historical period. Justificantes are retained because they carry
CSV and presentation evidence.

The design also supports previous-filing bindings without hardcoding special
cases into calculation formulas. A binding such as previous-year
economic-activity net income resolves through a typed observation provider and a
registry relation or binding selector, not through scattered Python logic.

## Consequences

Every modelo implementation wave must now depend on live filed-data capture
coverage. Before per-modelo work begins, the backend must prove it can capture,
hash, classify, and parse at least one full declaration artefact path into the
standard observation schema, with read-only guards active.

Modelo-specific waves then add extraction profiles and parser coverage for
their own submitted files and declaration PDFs. A modelo is not complete until
previous-filing and live-reference observations either resolve through the
standard schema or are recorded as an explicit evidence-backed gap that removes
the affected feature from filing-grade support.

This increases the pre-modelo infrastructure work, but it eliminates the unsafe
assumption that a CSV/justificante reader is enough to support legal
calculation bindings.
