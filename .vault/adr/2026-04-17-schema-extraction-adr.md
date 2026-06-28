---
name: schema-extraction-adr
description: Architecture Decision Record for programmatic AEAT modelo schema extraction (PDF/HTML → typed pydantic v2 model), wgergely/aeat#9
type: adr
tags:
  - "#adr"
  - "#schema-extraction"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-schema-extraction-research]]"
  - "[[2026-04-12-casilla-db-adr]]"
  - "[[2026-04-12-modelo-303-390-adr]]"
  - "[[2026-04-13-modelo-inventory-adr]]"
  - "[[2026-04-12-manual-practico-adr]]"
  - "[[2026-04-12-justificante-parser-adr]]"
---

# Architecture Decision Record: AEAT modelo schema extraction (#9)

## Status

Accepted. Self-audited 2026-04-17 via the `vaultspec-code-reviewer`
persona; ten MINOR/NIT findings were raised and are resolved inline
in the sections below (see §Audit for the resolution map).

## Context

The filing automation, draft builder (#39), submission engine (#42),
self-healing sync (#11), and casilla DB (#23) all currently depend on
a hand-rolled schema shape that lives in ad-hoc per-modelo Python
modules (`aeat.application.filing._builders._modelo_130_schema.py`) or curated
JSON files (`corpus/casillas/<modelo>/<period>.json`). Every new
modelo or filing period needs a human transcription of the AEAT
form; every transcription is an opportunity for drift. Issue #9 is
the foundational issue to replace transcription with extraction: a
typed, versioned pipeline that reads primary AEAT sources and emits
pydantic v2 records the rest of the codebase can trust.

Two closed catalogues are already on `main` and constrain the
design:

- `aeat.domain.modelos` (#6) owns `ModeloCode` — 20 enum members; every
  extracted `Modelo` MUST cite one of these.
- `aeat.domain.portals` (#7) owns `Portal` — every `ModeloCode` with a
  filing procedure has a matching `FILING` portal; the extracted
  `Modelo` MUST reference it.

The research doc
`[[2026-04-17-schema-extraction-research]]` surveyed three extraction
strategies (BOE Orden annex, live portal HTML probe, Manual práctico
+ LLM) and three library paths (pdfplumber, pymupdf, LLM). It
recommended anchoring extraction to the BOE-published Orden (the
legal source of truth), using `pdfplumber` which is already a
project dependency, and treating live-portal scraping as a verifier
rather than the primary source.

## Decision

We will implement a new public subpackage **`aeat.domain.schema`** that
owns the extracted modelo IR, the `Extractor` Protocol, and one
concrete `BoeOrdenExtractor` for Modelo 130 as proof-of-concept.
The full decision is enumerated below.

### 1. Package location and public API

- **Location**: `src/aeat/domain/schema/` (the directory exists on `main`
  with only a smoke test; this issue owns its first real contents).
- **Public API**: imports allowed *only* from `aeat.domain.schema` root.
  Underscore-prefixed submodules (`_models`, `_extractor`,
  `_boe_extractor`, `_cache`) are internal and unstable.
  `__all__` gates the public surface. Enforced by a smoke test.
- **Non-goal**: `aeat.domain.schema` is NOT a curated catalogue. It is an
  extraction pipeline + typed IR. The hand-reviewed catalogue is
  `aeat.domain.casillas` (#23).

### 2. Typed model hierarchy (pydantic v2 strict, mandatory)

Every type below is a `pydantic.BaseModel` with
`ConfigDict(strict=True, frozen=True, extra="forbid")`. **No
dataclasses. No bare dicts. No Optional where a sentinel is natural.**
This is the project-wide pydantic mandate (memory:
`pydantic_mandate`) restated for #9.

- **`SchemaSource`** — `StrEnum`:
  - `BOE_ORDEN` — the ministerial Orden approving the modelo
    (primary source, Strategy 1).
  - `PORTAL_HTML_PROBE` — reserved for live-portal verification
    (Strategy 2, not implemented in v1).
  - `MANUAL_LLM_DRAFT` — reserved for LLM-drafted prose rule
    extraction (Strategy 3, not implemented in v1).
  - `XSD_WIRE` — reserved for submission-format wire schemas
    (deferred to #42 cross-check).

- **`SchemaProvenance`** — provenance record:
  - `source: SchemaSource`
  - `origin_url: AnyHttpUrl` (the BOE or Sede URL the bytes
    were fetched from)
  - `document_ref: str` — human-canonical reference, e.g.
    `BOE-A-2023-15412` for Ordenes, `G601` for portal procedures
  - `sha256: str` — enforced via field regex `^[0-9a-f]{64}$`
  - `content_length: int` (`ge=1`)
  - `fetched_at: pydantic.AwareDatetime` — always tz-aware,
    normalised to UTC via a field validator that rejects naive
    datetimes.

- **`CasillaDataType`** — `StrEnum`. **Owned by `aeat.domain.schema`**;
  `aeat.domain.casillas.models.CasillaDataType` is the current home but
  will be re-exported from `aeat.domain.schema` in a follow-up (see §7).
  For v1 the `aeat.domain.schema.CasillaDataType` is a new StrEnum with
  identical members; the follow-up consolidation does the import
  flip and deletes the duplicate. Members:
  `CURRENCY_EUR`, `INTEGER`, `BOOLEAN`, `DATE`, `TEXT`, `SELECT`,
  `PERCENTAGE`. The duplication is an intentional blast-radius
  decision (do not touch #23 from #9); the adapter PR is tracked
  as `TODO(#9-followup)`. Conversion between the two enums uses
  string-value round-trip (`Other(str(member))`) — `isinstance`
  comparisons across the two are forbidden.

- **`FormulaNode`** — the evaluable AST the issue explicitly
  demands. Discriminated union tagged by `kind`:
  - `LiteralFormula(kind: Literal["literal"], value: Decimal)`
  - `CasillaRef(kind: Literal["ref"], casilla_id: str)`
  - `BinaryOp(kind: Literal["binop"], op: BinaryFormulaOp,
    left: FormulaNode, right: FormulaNode)`
  - `SumFormula(kind: Literal["sum"], terms:
    tuple[FormulaNode, ...])` — convenience for AEAT's common
    `Casilla_A + Casilla_B + ... + Casilla_N` totals.
  - `BinaryFormulaOp` is a `StrEnum{ADD, SUB, MUL, DIV}`.
  - Recursion resolved via `model_rebuild()` in
    `_models.py`.

  The AST is evaluable by walking it against a
  `Mapping[str, Decimal]` of casilla values. The evaluator lives
  in `_models.py` as a free function `evaluate(node, values)`.
  All four node kinds (`literal`, `ref`, `binop`, `sum`) are
  fully implemented in v1 — no `NotImplementedError` stubs — and
  each is directly exercised by `test_models.py`. `BinaryFormulaOp`
  division applies `Decimal` quantization with `ROUND_HALF_UP` and
  raises `SchemaEvaluationError` (a dedicated subclass of
  `SchemaError`, distinct from extraction and cache-validation
  errors) on division by zero or on a missing casilla_id lookup,
  with the target casilla ID included in the message when the
  caller passes the optional `casilla_id=` kwarg.

- **`ValidationRule`** — discriminated union tagged by `kind`:
  - `RangeRule(kind: "range", min: Decimal | None,
    max: Decimal | None)` — at least one bound required.
  - `RegexRule(kind: "regex", pattern: str)` — validated as a
    compilable regex at model-validation time.
  - `EnumRule(kind: "enum", values: tuple[str, ...])` — non-empty.
  - `CrossCasillaRule(kind: "cross", expression: FormulaNode,
    compare: CompareOp, rhs: FormulaNode)` — for rules of the
    form `Casilla_71 >= 0`.
  - `CompareOp` is a `StrEnum{EQ, NEQ, LT, LTE, GT, GTE}`.

- **`Casilla`**:
  - `casilla_id: str` — matches `^\d{2,4}$` (per the casilla-db
    regex on `main`)
  - `block: Translatable | None` — heading this casilla sits
    under in the BOE annex ("Operaciones interiores —
    IVA devengado")
  - `label: Translatable` — authoritative Spanish REQUIRED
    via `aeat.core.i18n.require_authoritative`, English and Hungarian
    MAY be empty in extracted records (reviewer / LLM fills them
    downstream).
  - `data_type: CasillaDataType`
  - `required: bool`
  - `computed: bool` — true iff `formula` is non-None.
  - `formula: FormulaNode | None`
  - `validations: tuple[ValidationRule, ...]`
  - `references_casillas: tuple[str, ...]` — casilla_ids this one
    mentions; must match formula references when formula is set.
  - `source_page: int | None` — page in the BOE PDF this casilla
    was extracted from (aids human review). REQUIRED (non-None,
    `ge=1`) when the owning `Modelo.provenance.source ==
    SchemaSource.BOE_ORDEN`; MAY be None for future sources that
    do not have page-level provenance. Enforced by a model-level
    validator on `Modelo`.

- **`Modelo`**:
  - `modelo_code: ModeloCode` (imported from `aeat.domain.modelos`)
  - `portal: Portal | None` (imported from `aeat.domain.portals`;
    nullable because Modelo 037 has no filing portal)
  - `period: str` — validated against `ModeloCode` cadence
    metadata (quarterly → `YYYYQ[1-4]`, annual → `YYYY`, monthly
    → `YYYY-MM`). The regex is delegated to a helper
    `validate_period_for_modelo(code, period)` that lives in
    `aeat.domain.schema._models` and consumes cadence metadata via the
    public `aeat.domain.modelos` API (`get_modelo(code).cadence`).
    Cadence logic MUST NOT be duplicated here — if a new regex
    is needed it is derived from the enum member, not redefined.
  - `casillas: tuple[Casilla, ...]` — non-empty.
  - `provenance: SchemaProvenance`
  - `extracted_at: pydantic.AwareDatetime`
  - `schema_version: int = 1` — the *shape* of this pydantic model;
    bumped when the model hierarchy changes (not per AEAT change).

  Model-level validators:
  - Casilla IDs unique.
  - `references_casillas` values exist in the same `Modelo`.
  - Every `formula` only references casillas present in the same
    `Modelo`.
  - Portal cross-ref: if `portal` is set, `Portal` metadata must
    carry `related_modelo == modelo_code`. Enforced via
    `aeat.domain.portals.get_portal`.

### 3. Extractor Protocol and concrete backend

- **`Extractor`** — a `typing.Protocol` (runtime-checkable) with a
  single `extract(self) -> Modelo` method. Constructors are
  per-backend and carry their own configuration.
- **`BoeOrdenExtractor`** — the sole concrete backend landed in v1:
  - Constructor: `BoeOrdenExtractor(pdf_path: Path, modelo_code:
    ModeloCode, period: str, boe_ref: str, origin_url:
    AnyHttpUrl)`.
  - `extract()` opens the PDF with `pdfplumber`, finds the annex
    start page by scanning for the heading `"ANEXO"` (Spanish),
    then walks lines via `page.extract_text()` through a small
    two-pass classifier (heading, numbered casilla declaration,
    formula). Matches Spanish formula prose against a regex
    library (`r"Casilla\s+(\d{2,4})\s*[=]\s*(.+)"` and the
    arithmetic operators), and returns a `Modelo` record.
    Same-page annex content (`"ANEXO I 01 Base..."`) is
    preserved via a post-match residue; duplicate declarations
    are tolerated when identical, rejected when conflicting.
    **Decision amendment (round-4 audit):** the original ADR
    specified `page.extract_tables()` for column geometry.
    Implementation switched to `page.extract_text()` + line
    classifier because (a) BOE Ordenes use legal-prose layout
    with inconsistent column alignment that degrades
    `extract_tables` output, (b) the line-based pattern library
    is simpler to extend for 303 / 390 follow-ups, and (c) every
    observed Modelo 130 layout fits the line shape. A
    table-geometry extractor is reserved for future modelos that
    genuinely require column-based parsing — it would subclass
    the line-based extractor rather than replace it.
  - The extractor is **deliberately narrow for v1**: it covers
    the patterns needed by Modelo 130. Follow-up PRs extend the
    pattern library for 303/390.
- **`LocalPdfFixtureExtractor`** (test-only, under
  `src/aeat/domain/schema/testing.py`) — takes a fixture path directly
  to keep unit tests hermetic. Unit tests in
  `src/aeat/domain/schema/test_boe_extractor.py` run against a small,
  redistributable PDF fixture checked into
  `tests/fixtures/schema/modelo_130_boe_a_2023_15412_annex.pdf`
  — extracted from the public BOE PDF and trimmed to the annex
  pages (BOE content is in the public domain per Ley 37/2007
  art. 13).

### 4. Persistence format

- Canonical cache directory:
  `var/schema-cache/modelo_<modelo_code.value>/`
  (e.g. `var/schema-cache/modelo_130/`). The `modelo_` prefix
  guarantees a valid directory name whatever the enum value
  shape and matches the research-doc convention.
- File name: `<boe_ref>.json` when source is `BOE_ORDEN`,
  `<document_ref>_<fetched_at_date>.json` otherwise.
- Format: `Modelo.model_dump_json(indent=2, by_alias=True)`
  with sorted keys (stable diff). Re-loadable with
  `Modelo.model_validate_json`.
- Manifest sidecar `<file>.manifest.json` records
  `SchemaProvenance` only — mirrors the `aeat.domain.manuals`
  pattern exactly.
- The cache root is configurable via **new settings** (§5).

### 5. Settings additions (`src/aeat/config.py`)

Three new env-backed settings, added to `Settings` and mirrored in
`env/.env.example` (enforced by `tests/test_config.py`):

- `aeat_schema_cache_dir: Path`
  - default `PROJECT_ROOT / "var" / "schema-cache"`
  - description: "Directory where extracted Modelo schemas and
    their provenance manifests are persisted."
- `aeat_schema_source_urls_override: str`
  - default `""`
  - description: "Optional JSON-encoded mapping of
    `{modelo_code: {boe_ref: url}}` that overrides the built-in
    BOE URL table (used for offline CI). The JSON-string shape is
    an intentional ergonomic compromise: env-vars are the only
    single-shape contract the rest of `aeat.core.config.Settings`
    uses; a typed nested settings model is deferred until the
    project adopts one project-wide."
- `aeat_schema_extraction_concurrency: int`
  - default `2`
  - `ge=1`
  - description: "Maximum number of BOE PDFs fetched in parallel
    by `aeat schema refresh`."

`aeat_schema_cache_dir` is added to the
`_normalize_repo_relative_paths` validator list.

### 6. CLI and refresh workflow

- New Typer subcommand group `aeat schema` authored in
  `src/aeat/entrypoints/cli/schema.py`, registered in
  `src/aeat/entrypoints/cli/__init__.py`. (The ADR originally proposed
  `aeat.domain.schema._cli` as the owning module; the plan-audit round
  moved the CLI into `aeat.entrypoints.cli.schema` to match the existing
  `aeat.entrypoints.cli.casillas` precedent and preserve public-API discipline
  — see plan §7.)
- Commands in v1:
  - `aeat schema refresh --modelo MODELO_130 --boe-ref
    BOE-A-2023-15412 --period 2025Q4` — fetch BOE PDF, extract,
    persist.
  - `aeat schema show --modelo MODELO_130 --boe-ref
    BOE-A-2023-15412` — pretty-print the cached `Modelo`. The
    cache key is `(modelo_code, boe_ref)`; `--period` is a
    refresh-time input, not a show-time lookup key.
- **Fetch helper** — `aeat.domain.schema._fetch.fetch_boe_pdf(boe_ref,
  origin_url, cache_dir) -> FetchedSchemaSource` mirrors the
  `aeat.domain.manuals._fetch` pattern exactly: streams the bytes via
  `httpx`, records sha256 + content length, returns a typed
  pydantic record carrying the on-disk path. `aeat schema
  refresh` composes `fetch_boe_pdf → BoeOrdenExtractor → persist`.
  A hard-coded table `BOE_ORDEN_SOURCES` in `_fetch.py` maps
  `(ModeloCode, boe_ref) → AnyHttpUrl`; the
  `aeat_schema_source_urls_override` setting (§5) lets CI / tests
  short-circuit the table.
- **Test-only PDF override** — `aeat schema refresh` accepts a
  hidden Typer option `--_pdf-path-override` (leading underscore,
  `hidden=True`). It is NOT exposed in `env/.env.example`, is NOT
  read from any env var, and tests assert that
  `Settings.env_var_names()` does not contain any name derived
  from it.
- `aeat schema diff` is **deferred** to a follow-up issue; only
  `refresh` and `show` are in scope for v1. This is a scope
  narrowing vs. the issue body, justified by the "deliberately
  conservative first cut" clause in the issue's "Notes" section,
  and recorded here for traceability.

### 7. Interaction with `aeat.domain.casillas` (#23)

- `aeat.domain.casillas.models.ModeloCode` (the local duplicate) is
  flagged for removal. The follow-up PR imports
  `aeat.domain.modelos.ModeloCode` and deletes the local StrEnum. **Not
  done in this PR** to keep the blast radius contained.
- `aeat.domain.casillas.models.FormulaReference` and
  `ValidationRuleReference` were explicitly authored as
  Protocol stubs pointing at #9. They are retained for v1;
  a follow-up PR re-points them at `aeat.domain.schema.FormulaNode` /
  `ValidationRule` by adapter. The adapter, not the model
  replacement, is the right shape because the casilla DB is a
  curated layer that may add reviewer-level fields the raw
  extracted model deliberately lacks.
- `aeat.domain.schema` MUST NOT import from `aeat.domain.casillas` (reverse
  dependency direction only). Enforced by smoke test.

### 8. Error hierarchy

`src/aeat/domain/schema/_errors.py` defines:

- `SchemaError(AeatError)` — base.
- `SchemaExtractionError(SchemaError)` — extractor failures
  (PDF parse error, annex not found, unexpected table layout).
- `SchemaCacheError(SchemaError)` — persistence / manifest
  failures.
- `SchemaValidationError(SchemaError)` — pydantic validation
  wrapped at loader boundary.
- `SchemaEvaluationError(SchemaError)` — runtime formula-AST
  evaluation failures (missing casilla lookup, division by zero).

Extractor failures MUST include the BOE ref and page number in
the exception message; pdfplumber exceptions are wrapped with
`raise ... from exc`.

### 9. Testing

- All new tests `@pytest.mark.unit`. **No mocks, no patches, no
  stubs.** Real fakes only (the fixture PDF is a real AEAT
  artefact, the `BoeOrdenExtractor` runs against a real
  `pdfplumber.open`).
- Coverage additions:
  - `test_models.py` — pydantic validators, formula evaluator
    happy-path for the four node kinds used by Modelo 130.
  - `test_boe_extractor.py` — extract → `Modelo` against the
    committed fixture PDF; assert casilla IDs, labels,
    formulas against a golden JSON also committed in fixtures.
  - `test_cache.py` — round-trip persistence.
  - `test_cli.py` — CLI `refresh` and `show` end-to-end with a
    `--pdf-path` override that short-circuits the network fetch
    (so no live dependency is introduced; the override is
    unit-test-only and NOT exposed through `env`).
  - `test_smoke.py` — `__all__` completeness, package docstring
    present, no imports of `aeat.domain.casillas`.
  - `test_config.py` — env var parity (the existing shared test
    picks up the three new fields automatically).

### 10. Commit message prefix

Per `CLAUDE.md`, conventional commits are mandatory. The
scaffolding commit uses `feat(schema): ...`; the #9 feature tag
is `#schema-extraction` in vault docs.

### 11. Project-wide convention compliance (restated)

Explicitly required on every module this PR touches:

- Google-style docstrings on every public symbol.
- `from __future__ import annotations` at the top of every file.
- `aeat.core.logging.get_logger(__name__)` for any module that emits
  logs — no `print`, no raw `logging.getLogger`.
- Domain errors inherit from `aeat.core.errors.AeatError`.
- Trilingual labels via `aeat.core.i18n.Translatable` with Spanish
  authoritative (`require_authoritative(..., domain="aeat")`).
- `@pytest.mark.unit` on every test — no `@pytest.mark.live`,
  no mocks, no patches, no stubs.
- Public API discipline: consumers outside `aeat.domain.schema` import
  only from the subpackage root.

## Consequences

**Positive**

- Filing automation can drop string-keyed casilla lookups and
  adopt a typed `Modelo.casillas` enumeration.
- The extraction pipeline is fully reproducible from immutable
  BOE artefacts — no live auth, no CI-hostile dependencies.
- The `FormulaNode` AST makes validator logic evaluable, not
  merely descriptive, satisfying the existing
  `filing-formula-divergence` finding already emitted by the
  filing draft validator.
- `aeat.domain.schema` cleanly owns the IR; `aeat.domain.casillas` cleanly
  owns the reviewer catalogue; `aeat.domain.modelos` + `aeat.domain.portals`
  own the identity enums. Each layer has one responsibility.

**Negative / accepted trade-offs**

- The PoC covers only Modelo 130; 303 / 390 follow-ups are
  required. This is explicit issue scope.
- The BOE annex parser is pattern-matched, not fully
  grammar-driven — it will fail on layouts the pattern library
  does not cover. Mitigation: `SchemaExtractionError` surfaces
  the failing page number so a human can investigate in minutes.
- Two modelo enums remain (`aeat.domain.modelos.ModeloCode` and
  `aeat.domain.casillas.models.ModeloCode`) until the #23-side
  follow-up merges.

**Deferred**

- `aeat schema diff` CLI.
- Strategy 2 (live portal probe) — scaffolded via
  `SchemaSource.PORTAL_HTML_PROBE` only.
- Strategy 3 (LLM draft) — scaffolded via
  `SchemaSource.MANUAL_LLM_DRAFT` only.
- XSD / wire-format extractor.
- `aeat.domain.casillas` integration (adapter PR).
- Scheduling / CI for refresh.

## Audit

Self-audit performed per the issue's "ZERO HUMAN IN THE LOOP"
mandate. Checklist:

- [x] Every boundary-crossing type is a pydantic v2 model
  (`strict=True, frozen=True`). ✓
- [x] `ModeloCode` from `aeat.domain.modelos` is the authoritative
  identity; `aeat.domain.schema.Modelo.modelo_code` types against it. ✓
- [x] `Portal` from `aeat.domain.portals` is referenced from
  `aeat.domain.schema.Modelo.portal`; enum invariants enforced via
  `get_portal`. ✓
- [x] Scope matches issue #9 acceptance criteria: research doc
  (present), ADR (this doc), `src/aeat/domain/schema/` types, one
  working extractor (Modelo 130), settings additions,
  `.env.example` alignment, refresh workflow documented. ✓
- [x] Deferrals explicit: `schema diff`, live probe, LLM drafts,
  XSD, `aeat.domain.casillas` adapter. ✓
- [x] No dependencies added beyond what is already in
  `pyproject.toml`. ✓
- [x] Unit tests declared, live tests explicitly out of scope
  for v1 (fixture PDF is committed). ✓
- [x] `@pytest.mark.unit` markers planned; banned-import rules
  not violated. ✓
- [x] Google-style docstrings and logging conventions restated
  in §11. ✓

### Audit finding resolution map (2026-04-17)

A first-pass self-audit via the `vaultspec-code-reviewer`
persona produced ten findings. Each is resolved inline:

| # | Severity | Resolution |
|---|----------|-----------|
| 1 | MINOR | §2 CasillaDataType bullet — blessed string-value round-trip recorded; `isinstance` cross-comparison forbidden. |
| 2 | MINOR | §2 Modelo.period bullet — helper owned by `aeat.domain.schema._models`; cadence logic non-duplication rule stated. |
| 3 | MINOR | §4 persistence — path nailed to `var/schema-cache/modelo_<value>/<boe_ref>.json`. |
| 4 | MINOR | §2 FormulaNode evaluator — `NotImplementedError` branch removed; all four kinds implemented. Division-by-zero wraps `SchemaExtractionError`. |
| 5 | MINOR | §6 — fetch helper named (`aeat.domain.schema._fetch.fetch_boe_pdf`); composition order stated. |
| 6 | MINOR | §6 — test-only override pinned to `--_pdf-path-override` hidden flag; env-exposure forbidden. |
| 7 | NIT | §2 Casilla.source_page — required when `SchemaSource.BOE_ORDEN`; model-level validator enforces. |
| 8 | NIT | §2 SchemaProvenance.fetched_at — typed as `pydantic.AwareDatetime`; sha256 field regex added. |
| 9 | NIT | §11 added — Google docstrings, logging, `AeatError`, Translatable, `@pytest.mark.unit`, public API discipline restated. |
| 10 | NIT | §5 — `aeat_schema_source_urls_override` JSON-string shape called out as an ergonomic compromise (a typed nested settings model is rejected for now because env vars are the single-shape contract the rest of the project uses). |

Verdict post-amendment: PASS, mergeable.

## References

- `[[2026-04-17-schema-extraction-research]]` — the source of
  strategy trade-offs and library survey.
- `[[2026-04-13-modelo-inventory-adr]]` — `ModeloCode` enum
  shape this ADR depends on.
- `[[2026-04-12-casilla-db-adr]]` — the downstream curated
  catalogue this extractor feeds.
- `src/aeat/domain/manuals/_fetch.py` — the sha256-verified fetch
  pattern this issue mirrors.
