---
name: schema-extraction-research
description: Research into programmatic extraction of AEAT modelo schemas (casillas, validation rules, formulas) from PDF forms, Sede HTML, and instructions, for wgergely/aeat#9
type: research
tags:
  - "#research"
  - "#schema-extraction"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-12-casilla-db-research]]"
  - "[[2026-04-12-modelo-303-390-research]]"
  - "[[2026-04-13-modelo-inventory-research]]"
  - "[[2026-04-12-justificante-parser-research]]"
  - "[[2026-04-12-manual-practico-research]]"
---

# schema-extraction research (#9)

Date: 2026-04-17
Branch: `feature/9-schema-extraction`
Issue: wgergely/aeat#9

## Question

What is the lowest-risk, highest-fidelity pipeline for programmatically
extracting every AEAT *modelo*'s per-period structure — casilla IDs,
labels, data types, validation rules, calculation formulas — and
persisting it as typed, versioned Python models that the filing engines
can rely on as ground truth?

## Scope boundary (what this subpackage is NOT)

Three adjacent subpackages already exist on `main` and define the
boundary:

- `aeat.domain.modelos` (#6) — the closed catalogue of `ModeloCode` enum
  members + pydantic metadata (cadence, profile applicability, legal
  citations). Answers "which modelos exist and when are they filed";
  knows nothing about the internal box layout of a form.
- `aeat.domain.portals` (#7) — the closed catalogue of AEAT portal URLs
  (`Portal` enum) including one FILING portal per `ModeloCode`.
  Answers "where on sede.agenciatributaria.gob.es do I present this
  form"; knows nothing about what boxes the form contains.
- `aeat.domain.casillas` (#23) — the **hand-curated, human-reviewed**
  JSON corpus of canonical `CasillaRecord` rows with trilingual
  labels, reviewed-by metadata, and Protocol-based `FormulaReference`
  / `ValidationRuleReference` stand-ins that explicitly point at
  *this* issue as their forcing function.

Issue #9 sits *upstream* of `aeat.domain.casillas`: it owns the extraction
pipeline that reads primary AEAT sources and emits typed `Modelo`
records. The downstream reviewer workflow in `aeat.domain.casillas` either
adopts those records verbatim (once extractor fidelity is proven)
or uses them as LLM-drafted candidates for a human reviewer.

**Operative rule**: `aeat.domain.schema` owns the extracted IR; it MUST
NOT duplicate `aeat.domain.casillas.CasillaRecord` fields that are
review-only (e.g. `reviewed_by`, `llm_draft_provenance`). Those
belong to the downstream curated layer.

## Candidate sources of truth

Three representative modelos were surveyed (per the issue): 130
(quarterly IRPF fraccionado estimación directa), 303 (quarterly IVA
general), 390 (annual IVA summary). For each, the following source
families exist on AEAT and BOE:

### Source A: the "Ayuda técnica" / portal HTML form (Sede)

The live filing portal (`portal_m130_pago_fraccionado_ed` → G601,
`portal_m303_iva_autoliquidacion` → G414, `portal_m390_resumen_iva`
→ G415 / H390) renders the interactive form in HTML/JS after
authentication. For the 2025 campaign the 303 and 130 forms are
rendered client-side with fetched JSON schemas embedded into the
DOM via `window.schema` / `APP_STATE` — observable only after a
certificate-backed login.

**Coverage**: highest. Exposes casilla IDs, labels (Spanish only),
data types implicitly (via HTML input `type`, `maxlength`, regex
patterns), inter-casilla references (via `oninput` / `onblur`
formulas), and the authoritative "this casilla is computed" flag.
**Stability**: poor. The DOM of the live forms changes every campaign
and often mid-campaign with zero migration notes. Obfuscated JS.
**Extractability**: requires Playwright + client-cert auth (#8);
live-only, not reproducible without authenticating. DOM scraping is
brittle against AEAT layout changes (#17 anti-bot guidance applies).
**Verdict**: high-fidelity but **unsuitable as primary source** —
it is the verification source, not the extraction source.

### Source B: the BOE "Orden" that approves the modelo (annex)

Every AEAT modelo is approved annually (or multi-annually) via a
ministerial *Orden HAC/XXX/YYYY* published in the Boletín Oficial
del Estado. The Orden's **Annex I** reprints the official form
layout: the full list of numbered casillas, a short Spanish label
for each, and — critically — the arithmetic formulas
(`Casilla 03 = Casilla 01 × 0,04`) expressed in Spanish prose.

Representative orders (confirmed via `gh`-accessible research and
the `aeat.domain.casillas` corpus' citation fields):

- **Modelo 130**: Orden EHA/672/2007 (base) → Orden HAC/665/2023
  (updated layout for 2024+). BOE-A-2023-15412. Stable PDF at
  `boe.es/diario_boe/txt.php?id=BOE-A-2023-15412`.
- **Modelo 303**: Orden HAC/819/2024 (2025 campaign). BOE-A-2024-16220.
- **Modelo 390**: Orden HAC/1/2024 (modifications for 2025). BOE-A-2024-325.

**Coverage**: full legal specification. All casillas, official
Spanish labels, legal formulas. **Stability**: excellent — a BOE PDF
is immutable once published; when the form changes, a new Orden is
issued and the old one is superseded. **Extractability**: text-layer
PDFs, high-quality OCR unnecessary; `pdfplumber` extracts
layout-anchored text cleanly because the BOE typeset is consistent
(`Times` body, two-column legal text, tables for the annex). Tables
of casillas in the Annex are rendered as real `<table>`-equivalent
layouts with detectable column geometry. Formula prose is stable
Spanish: `Casilla <n> = Casilla <m> × 0,<rate>`.
**Verdict**: strongest candidate for **primary source**. Immutable,
legally authoritative, versioned by BOE-A ID.

### Source C: AEAT "Manual práctico" (IRPF / IVA, annual)

AEAT publishes annual practical manuals (e.g. *Manual práctico
IVA 2025*, already corpus-ised under `aeat.domain.manuals` via #25) that
walk through each modelo's filing procedure. These explain
casillas in prose, often with worked examples and cross-references
to BOE articles (Ley 37/1992 for IVA, Ley 35/2006 for IRPF).

**Coverage**: rich for prose rules and validations ("Si el
resultado de la casilla 71 es negativo, marque la casilla 73"),
but weaker on the exhaustive casilla list — the manual explains
what matters, not the complete form. **Stability**: annual;
already fetched via sha256-verified manifests by `aeat.domain.manuals`.
**Extractability**: same PDF-text pipeline as Source B, plus
prose-to-rule parsing that currently requires LLM assistance
(non-deterministic). **Verdict**: strong **secondary source**
for validation rules and narrative context that the BOE annex
omits — NOT for the casilla list itself.

### Source D: XSD / submission-format schemas

AEAT publishes the electronic submission schemas (the XML/SOAP
formats used by the filing HTTP endpoints under
`www2.agenciatributaria.gob.es/.../preDeclaracionFase0`) as a
set of `.xsd` files referenced from the "Ayudas técnicas"
section. These define the wire format — field names, regex
constraints, types — but use cryptic internal field codes
(`FechaDevengo`, `BaseGeneralSujeta20`) that do not match the
casilla IDs a human filer sees on the portal.

**Coverage**: perfect for wire-format validation; no casilla IDs
or human labels. **Stability**: high — changes require client
migration notices. **Extractability**: trivial (`xmlschema`
parses XSD into Python dicts). **Verdict**: **reserved** as a
late-stage cross-check for the submission engine (#42), not for
casilla-level schema extraction.

## Library survey

Existing project dependencies (`pyproject.toml`):

- `pdfplumber>=0.11.9` — layout-aware text + table extraction.
  Already in use by `aeat.domain.justificante` (#44) and `aeat.domain.manuals`
  (#25). Handles text-layer PDFs well; falls over on scanned /
  image-only PDFs (requires `tesseract` fallback, which is NOT a
  project dependency).
- `playwright>=1.58.0` — used by `aeat.adapters.outbound.aeat.browser` and `aeat.status`
  for authenticated AEAT navigation. Required for Source A.
- `beautifulsoup4>=4.12` — HTML parser used by
  `aeat.status._parsers`. Sufficient for static HTML, but not for
  AEAT's JS-rendered portal forms.
- `httpx>=0.28.1` — used by `aeat.domain.manuals._fetch` to stream BOE /
  Sede PDFs with sha256 verification.
- `lxml` — NOT a direct dependency (transitive via `playwright`
  only); avoid for now.
- `camelot` / `tabula-py` — NOT present; would add Java / Ghostscript
  requirements the project has so far rejected. `pdfplumber`'s
  built-in table extractor is adequate for BOE two-column legal
  tables.
- `pymupdf` (`fitz`) — NOT present; `pdfplumber` uses `pdfminer.six`
  and is adequate. Adding `pymupdf` would duplicate capability and
  complicate the AGPL footprint.
- `pypdf` — NOT present; `pdfplumber` dominates.
- `unstructured` — NOT present; too heavyweight (ML models, OCR).

**No new dependencies are required for the Source B path**. The
`aeat.domain.schema` extractor can ride entirely on `pdfplumber` +
`httpx` which are already in the wheel.

The project's `aeat.adapters.outbound.llm` subpackage (with Anthropic / OpenAI /
Gemini providers and cache) is the designated path for any
prose-to-rule extraction from Source C — consistent with the
"LLM-as-draft-only" convention in `aeat.domain.casillas`.

## Three candidate extraction strategies

### Strategy 1 — "BOE-first, deterministic"

**Pipeline**: fetch the BOE PDF of the Orden that approves the
modelo → locate Annex I in the PDF (page anchor: "ANEXO I") →
`pdfplumber.extract_tables` on the annex pages → parse each row
into a `Casilla` (ID, label, block heading, formula prose if
present) → string-match a small library of Spanish arithmetic
phrases into `Formula` records → persist as JSON under
`var/schema-cache/modelo_<n>/<boe-a-id>.json` keyed by BOE-A
identifier.

**Pros**: fully deterministic; no auth; no JS rendering; no LLM
dependency; reproducible from an immutable BOE artefact;
trivially diffable when AEAT republishes; idiomatic with the
existing `aeat.domain.manuals` fetch+manifest pattern.
**Cons**: no coverage for portal-only casillas that the BOE
annex omits (very rare, seen in 303 for the box-97 conditional
display); prose formulas need a small rule-matching engine
(not full NLP) to catch patterns like `Casilla X = Casilla Y +
Casilla Z`.
**Cost**: medium upfront (writing the `pdfplumber` table walker
+ the formula pattern matcher), low ongoing.

### Strategy 2 — "Portal-HTML scrape"

**Pipeline**: authenticate with client cert (#8) → Playwright to
the G601/G414/G415 entry points → `page.evaluate` to dump
`window.APP_STATE` and bound input regexes → reconstruct
`Casilla` records.

**Pros**: highest fidelity — captures every casilla the user
actually sees, including portal-only conditionals.
**Cons**: requires live auth on every refresh; DOM layout is
unstable across campaigns and a single overnight update can
invalidate all selectors; violates the project's "live tests
never contain mocks" + "live-AEAT-write safety" posture because
a scrape run would constitute an authenticated probe; cannot
run in CI.
**Cost**: high upfront, very high ongoing.

### Strategy 3 — "Manual práctico + LLM"

**Pipeline**: use the `aeat.domain.manuals` corpus (already fetched,
sha256-verified) → feed the modelo's chapter to an `aeat.adapters.outbound.llm`
prompt that extracts a JSON casilla list → cache through
`aeat.adapters.outbound.llm`'s cache layer → persist.

**Pros**: covers prose validation rules that Strategy 1 misses;
reuses the already-landed LLM infrastructure.
**Cons**: non-deterministic; LLM hallucination on casilla IDs is
a real and documented risk for AEAT forms (the manuals often
misprint box numbers); cannot be the single source of truth; no
legal authority — the BOE is.
**Cost**: low upfront, moderate ongoing (prompt drift, LLM
version pinning).

## Recommendation

**Strategy 1 (BOE-first) is the primary path, Strategy 3 is the
secondary-enrichment path, Strategy 2 is the verification path.**

Rationale:

- The BOE Orden is the *legal* source of truth: AEAT cannot
  lawfully accept a casilla that is not in the approved modelo
  annex. Anchoring extraction to the BOE makes the pipeline's
  correctness a verifiable property, not a scrape quality metric.
- Strategy 1 requires zero new runtime dependencies, zero live
  auth, and produces an immutable, diff-friendly JSON artefact
  per BOE-A ID — identical in spirit to the `aeat.domain.manuals`
  sha256 manifest pattern.
- Strategy 3 is retained behind an explicit `SchemaSource.MANUAL_LLM`
  enum value so narrative validation rules (the things the BOE
  annex does not spell out) can be added incrementally with
  clear provenance. LLM drafts are never canonical; they feed a
  future reviewer workflow that parallels `aeat.domain.casillas verify`.
- Strategy 2 is retained as a `SchemaSource.PORTAL_HTML_PROBE`
  live-test target (`@pytest.mark.live`) that asserts the
  BOE-extracted casilla IDs match the live portal for the current
  campaign — catching mid-campaign portal patches without making
  the scraper a runtime dependency.

**Proof-of-concept modelo**: Modelo 130. Rationale:

- Smallest of the three surveyed modelos (~20 casillas vs. 85
  for 303 and 500+ for 390).
- Arithmetic-only formulas (no IVA rate tables, no intra-form
  recargo equivalencia annexes).
- Orden HAC/665/2023 is stable and freely downloadable from BOE
  without JavaScript, client cert, or rate limits.
- `aeat.domain.casillas` already has a hand-curated `MODELO_130/2025Q4`
  catalogue (reviewed on `main`) that can serve as the extractor
  oracle — the PoC passes if the BOE-extracted casillas match
  the reviewed curated set casilla-for-casilla, after
  normalisation.

## Typed model shape (informs the ADR, not prescriptive)

The extraction pipeline's output must be a pydantic v2 strict
model hierarchy. Preliminary shape:

- `SchemaSource` — StrEnum: `BOE_ORDEN`, `MANUAL_LLM_DRAFT`,
  `PORTAL_HTML_PROBE`, `XSD_WIRE`.
- `SchemaProvenance` — where this record came from + when +
  sha256 + BOE-A id or URL.
- `CasillaDataType` — closed set mirroring the existing enum in
  `aeat.domain.casillas.models` (`CURRENCY_EUR`, `INTEGER`, `BOOLEAN`,
  `DATE`, `TEXT`, `SELECT`, `PERCENTAGE`). The two subpackages
  MUST share this enum; the ADR picks the canonical owner.
- `FormulaNode` — recursive strict union: `LiteralFormula(value)`,
  `CasillaRef(casilla_id)`, `BinaryOp(op, left, right)` with
  `op in {add, sub, mul, div}`. This is the *evaluable AST* the
  issue explicitly requires — not a raw string.
- `ValidationRule` — strict union tagged by `kind`: `RangeRule`,
  `RegexRule`, `EnumRule`, `CrossCasillaRule`.
- `Casilla` — ID, block heading, label (authoritative Spanish
  per `aeat.core.i18n.Translatable`, English and Hungarian optional
  and drafted downstream), data type, required, computed,
  formula (nullable), validations (tuple), references (tuple of
  casilla IDs).
- `Modelo` — `ModeloCode` (cross-reference to #6), `Portal`
  (cross-reference to #7), `period` (string validated against the
  cadence in `aeat.domain.modelos.ModeloCode` metadata), `casillas`
  (tuple), `provenance` (SchemaProvenance), `extracted_at`,
  `version` (BOE-A id when provenance is BOE).
- `Extractor` — Protocol with a single `extract(source: Source) ->
  Modelo` method so backends are swappable. A concrete
  `BoeOrdenExtractor(pdf_path, modelo_code)` implements the PoC.

### Naming collision risk

`aeat.domain.casillas.models.ModeloCode` currently duplicates
`aeat.domain.modelos.ModeloCode` with a reduced membership. The #23 author
explicitly flagged this as "temporary until #9 lands" in
`_protocols.py` / `models.py`. The ADR for #9 MUST resolve this
by importing `aeat.domain.modelos.ModeloCode` and deprecating the local
copy — out of scope for the first PR, but recorded as a
follow-up in the ADR's "future work" section.

## Refresh workflow

- CLI: `aeat schema refresh --modelo 130 --boe-ref BOE-A-2023-15412`
  (explicit BOE reference; no date arithmetic). Downloads the
  BOE PDF through `httpx`, writes a sha256 manifest next to the
  JSON (mirrors `aeat.domain.manuals._fetch` exactly), runs the
  extractor, writes `schema-cache/modelo_130/<BOE-A-id>.json`.
- `aeat schema diff --modelo 130 --against main` — diffs the
  current on-disk schema against `HEAD` (git blobs) so a human
  reviewer can see casilla additions/removals/formula changes
  before merge.
- Detecting new periods: out of scope for #9; the issue explicitly
  calls out scheduling / CI integration as a follow-up.
  Recommendation: a future `aeat.application.sync`-hosted probe reads the
  BOE RSS feed for `agenciatributaria` publishers.

## Out of scope

- Full schema for 303 / 390 beyond "extractor validated against
  the curated `aeat.domain.casillas` subset that already exists".
- Live portal probe (Strategy 2) — scaffolded as a future
  `@pytest.mark.live` target, no code in this PR.
- LLM-assisted validation rule extraction (Strategy 3) — the
  `SchemaSource.MANUAL_LLM_DRAFT` enum slot is reserved, but the
  extractor is not implemented.
- Resolving the `ModeloCode` duplication in `aeat.domain.casillas.models`
  — follow-up issue.
- Any UI / Obsidian view for the schema.

## References

- `.vault/research/2026-04-12-casilla-db-research.md` — the
  adjacent curated-casilla-corpus research doc that forced the
  pydantic stubs forcing this work.
- `.vault/research/2026-04-12-modelo-303-390-research.md` — the
  hand-compiled casilla layouts used here as the extractor oracle.
- `.vault/research/2026-04-13-modelo-inventory-research.md` —
  the `ModeloCode` enum provenance.
- `src/aeat/domain/manuals/_fetch.py` — the sha256-verified PDF fetch
  pattern this issue's refresh workflow mirrors exactly.
- `src/aeat/domain/casillas/models.py` — the downstream curated record
  shape that `aeat.domain.schema.Casilla` feeds into.
- BOE-A-2023-15412 — Orden HAC/665/2023 approving the 2024+
  Modelo 130 layout.
- BOE-A-2024-16220 — Orden HAC/819/2024 approving the 2025
  Modelo 303 layout.
- BOE-A-2024-325 — Orden HAC/1/2024 modifying Modelo 390.
