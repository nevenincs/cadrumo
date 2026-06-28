---
name: schema-extraction-plan
description: Implementation plan for the aeat.domain.schema subpackage (pydantic models, Extractor interface, BOE-Orden PoC extractor for Modelo 130), wgergely/aeat#9
type: plan
tags:
  - "#plan"
  - "#schema-extraction"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-schema-extraction-adr]]"
  - "[[2026-04-17-schema-extraction-research]]"
  - "[[2026-04-12-casilla-db-adr]]"
  - "[[2026-04-13-modelo-inventory-adr]]"
---

# Implementation plan: `aeat.domain.schema` subpackage (#9)

Single-phase, single-PR plan. Branch
`feature/9-schema-extraction`. Every step is scoped so a strict
reviewer can diff it independently.

## Pre-flight constraints (READ BEFORE EXECUTING)

- Pydantic v2 strict + frozen on every boundary type. No
  dataclasses, no bare `dict[str, Any]`.
- **Single documented exception**: `aeat.core.i18n.Translatable` is a
  TypedDict by project convention (`CLAUDE.md`, trilingual
  contract); `Casilla.label` / `Casilla.block` use it as
  declared in the ADR §2. This is the only blessed non-pydantic
  boundary shape.
- Every new test carries exactly one `@pytest.mark.unit` marker.
  No mocks / patches / stubs. Use real inputs (real `pdfplumber`
  over real synthetic PDFs generated with `reportlab`).
- **Test library ban (global)**: every `test_*.py` file under
  `src/aeat/domain/schema/` MUST NOT import `unittest`, `unittest.mock`,
  `mock`, `pytest_mock`, `pytest_httpx`, `responses`,
  `httpx_mock`, `time_machine`, `freezegun`, `vcr`. `httpx`
  handles `file://` URLs natively — local PDF fetches are tested
  end-to-end against a real `file://` URL served from `tmp_path`,
  not against a mocked HTTP server.
- `from __future__ import annotations` at the top of every new
  `.py` file.
- Google-style docstrings on every public symbol.
- `aeat.core.logging.get_logger(__name__)` for any module that emits
  logs. Domain errors inherit from `aeat.core.errors.AeatError`.
- Public API discipline: `aeat.domain.schema`'s public surface is the
  `__all__` tuple in `src/aeat/domain/schema/__init__.py`. Consumers
  MUST NOT import from underscore-prefixed submodules.
- `aeat.domain.schema` MUST NOT import from `aeat.domain.casillas`. The
  reverse is already the case (#23 uses Protocol stubs pointing
  at #9). Smoke-test enforces.
- Conventional commits. The squash commit for this PR is
  `feat(schema): extract AEAT modelo schemas from BOE Ordenes (#9)`.

## Step 1 — scaffold subpackage structure

Create the following files under `src/aeat/domain/schema/`:

- `__init__.py` — module docstring, `__all__` tuple re-exporting
  every public name, smoke-import wiring. Replaces the current
  stub. Re-exports (all lazy-importable from flat submodules for
  now; switch to `__getattr__` lazy only if circular imports
  appear):
  - `CasillaDataType`, `BinaryFormulaOp`, `CompareOp`,
    `SchemaSource`
  - `SchemaProvenance`, `SchemaVersion` (a small pydantic
    record: `(schema_version: int, boe_ref: str | None)`)
  - `FormulaNode` union type alias,
    `LiteralFormula`, `CasillaRef`, `BinaryOp`, `SumFormula`,
    `evaluate`
  - `ValidationRule` union type alias,
    `RangeRule`, `RegexRule`, `EnumRule`, `CrossCasillaRule`
  - `Casilla`, `Modelo`
  - `Extractor` Protocol
  - `BoeOrdenExtractor`
  - `fetch_boe_pdf`, `FetchedSchemaSource`, `BOE_ORDEN_SOURCES`
  - `SchemaError`, `SchemaExtractionError`, `SchemaCacheError`,
    `SchemaValidationError`
  - `load_modelo_from_cache`, `save_modelo_to_cache`,
    `resolve_schema_cache_file`
- `_errors.py` — error hierarchy rooted on `aeat.core.errors.AeatError`.
- `_enums.py` — `SchemaSource`, `CasillaDataType`,
  `BinaryFormulaOp`, `CompareOp`. All StrEnum.
- `_models.py` — all pydantic models
  (`SchemaProvenance`, `SchemaVersion`, every
  `FormulaNode` variant, every `ValidationRule` variant,
  `Casilla`, `Modelo`), the `evaluate(node, values)` free
  function, and the `validate_period_for_modelo` helper.
  `FormulaNode` and `ValidationRule` are `Annotated[Union[...],
  Field(discriminator="kind")]` tagged unions. Call
  `LiteralFormula.model_rebuild()` etc. after the union is
  declared to resolve forward refs.
- `_extractor.py` — the `Extractor` Protocol.
- `_boe_extractor.py` — the `BoeOrdenExtractor` class.
  Depends on `pdfplumber`. Row-classifier lives here as
  private helpers `_classify_row`, `_parse_formula_prose`,
  `_normalise_amount`.
- `_fetch.py` — `BOE_ORDEN_SOURCES` table, `FetchedSchemaSource`
  model, `fetch_boe_pdf(boe_ref, origin_url, cache_dir,
  settings) -> FetchedSchemaSource`. Mirrors
  `aeat.domain.manuals._fetch` patterns: streams via `httpx`, hashes
  while streaming, returns a typed record, never mocks.
- `_cache.py` — `load_modelo_from_cache`, `save_modelo_to_cache`,
  `resolve_schema_cache_file(code: ModeloCode, boe_ref: str,
  root: Path) -> Path`.
- **(removed)** `_cli.py` — the Typer sub-app lives in
  `src/aeat/entrypoints/cli/schema.py` instead. This keeps `aeat.domain.schema`
  free of Typer as a runtime dependency of the domain code and
  matches the `aeat.entrypoints.cli.casillas` precedent.
- `testing.py` — re-exports `build_fake_boe_pdf` fixture-builder
  (uses `reportlab`) and `EXPECTED_MODELO_130_CASILLAS` golden
  data used by unit tests. Not imported by the production
  code path.
- `test_models.py` — pydantic validators, formula AST, evaluator.
- `test_boe_extractor.py` — end-to-end extraction against a
  generated PDF.
- `test_cache.py` — round-trip persistence.
- `test_cli.py` — Typer CLI exercises with `CliRunner`.
- `test_smoke.py` — `__all__` completeness, `aeat.domain.casillas`
  non-import assertion, docstring presence.

Why colocated tests: matches `aeat.domain.casillas`, `aeat.domain.manuals`,
`aeat.domain.modelos`, `aeat.domain.portals` conventions (Rust-style colocated
tests) and the `conftest.py` banned-import enforcement.

## Step 2 — enums and errors

Minimal; no behaviour. Purpose: keep the dependency order linear
so subsequent modules import only from earlier-numbered ones.

Module dependency DAG (strictly top-down):
`_errors` ← `_enums` ← `_models` ← `_fetch`, `_cache`,
`_extractor`, `_boe_extractor` ← `__init__` (re-exports).
`src/aeat/entrypoints/cli/schema.py` consumes the public surface only.

## Step 3 — pydantic models and formula evaluator

`_models.py` content order:

1. `SchemaSource`, `BinaryFormulaOp`, `CompareOp`,
   `CasillaDataType` are imported from `_enums`.
2. `_StrictFrozenModel` private base:
   `ConfigDict(strict=True, frozen=True, extra="forbid")`.
   Copied pattern from `aeat.domain.casillas.models._StrictFrozenModel`
   so reviewers recognise the shape.
3. `SchemaProvenance` (`source`, `origin_url`,
   `document_ref`, `sha256` with regex, `content_length` ≥ 1,
   `fetched_at: AwareDatetime`).
4. `SchemaVersion` (`schema_version: int = 1`, `boe_ref: str | None`).
5. Formula nodes:
   - `LiteralFormula(kind: Literal["literal"], value: Decimal)`
   - `CasillaRef(kind: Literal["ref"], casilla_id: str)` —
     `casilla_id` regex `^\d{2,4}$`.
   - `BinaryOp(kind: Literal["binop"], op: BinaryFormulaOp,
     left: "FormulaNode", right: "FormulaNode")`.
   - `SumFormula(kind: Literal["sum"], terms:
     tuple["FormulaNode", ...])` — non-empty.
   - `FormulaNode = Annotated[LiteralFormula | CasillaRef |
     BinaryOp | SumFormula, Field(discriminator="kind")]`.
   - After the alias is declared, call `model_rebuild()` on
     **every** model that directly or transitively holds a
     `FormulaNode` field, in declaration order:
     `BinaryOp`, `SumFormula`, `CrossCasillaRule`,
     `Casilla`, `Modelo`. Matches the pattern proven in
     `aeat.domain.casillas.models`.
6. `evaluate(node, values) -> Decimal`:
   - `LiteralFormula` → `node.value`.
   - `CasillaRef` → `values[node.casilla_id]` with
     `KeyError` wrapped as `SchemaValidationError`.
   - `BinaryOp` ADD/SUB/MUL/DIV — DIV with explicit
     `ZeroDivisionError → SchemaExtractionError("division by
     zero at casilla ...")`; DIV result quantised to
     `Decimal("0.01")` with `ROUND_HALF_UP`.
   - `SumFormula` — sum of evaluated terms.
7. Validation rules:
   - `RangeRule(kind: "range", min_: Decimal | None,
     max_: Decimal | None)` with `model_validator` asserting
     at least one bound and `min_ <= max_` when both set.
     Pydantic's field names `min` / `max` shadow builtins and
     cause linter noise; use `min_` / `max_` with
     `Field(alias="min")` / `Field(alias="max")`, declare
     `ConfigDict(..., populate_by_name=True)` on
     `_StrictFrozenModel`, and pass `by_alias=True` on
     **every** `model_dump` / `model_dump_json` call site so
     on-disk JSON keys stay clean (`min`, `max`) and
     round-trip cleanly with either alias or field name on
     input.
   - `RegexRule(kind: "regex", pattern: str)` — `field_validator`
     compiles the pattern at construction time.
   - `EnumRule(kind: "enum", values: tuple[str, ...])` —
     non-empty, deduplicated.
   - `CrossCasillaRule(kind: "cross", expression: FormulaNode,
     compare: CompareOp, rhs: FormulaNode)` — field name
     `expression` matches ADR §2 exactly.
   - `ValidationRule = Annotated[... , Field(discriminator="kind")]`.
8. `Casilla` fields per ADR §2; model-validator asserts the
   biconditional `computed iff formula is not None` (not XOR),
   and that `references_casillas` covers every `CasillaRef`
   found under the formula AST (walker implemented as
   `_collect_refs(node)`).
9. `Modelo` fields per ADR §2; model-validator enforces:
   - `casillas` non-empty.
   - All `casilla_id` unique.
   - Every `references_casillas` entry exists.
   - Every `CasillaRef.casilla_id` under every `Casilla.formula`
     exists.
   - When `provenance.source == BOE_ORDEN`, every
     `Casilla.source_page` is non-None.
   - When `portal` is set, `get_portal(portal).related_modelo
     == modelo_code` (imported lazily inside the validator to
     avoid circular import).
   - `period` is accepted by
     `validate_period_for_modelo(modelo_code, period)`.
10. `validate_period_for_modelo(code, period) -> None`:
    - Resolve `cadence = get_modelo(code).cadence` (public
      `aeat.domain.modelos` API).
    - For `QUARTERLY`: regex `^\d{4}Q[1-4]$`.
    - For `ANNUAL`: regex `^\d{4}$`.
    - For `MONTHLY`: regex `^\d{4}-(0[1-9]|1[0-2])$`.
    - For `AD_HOC`: regex `^\d{4}$` (year-only audit stamp).
      Additive to the ADR §2 list — ADR §2 enumerated the
      three cadences relevant to the Modelo 130 PoC; the
      extractor helper must handle all four `ModeloCadence`
      members to pass the smoke import boundary. The `AD_HOC`
      regex is scoped to its cadence (looked up per call),
      so its overlap with the `ANNUAL` shape is not a
      disambiguation problem.

Cadence regex logic is derived from the enum; no parallel
mapping table.

## Step 4 — fetch + cache

`_fetch.py`:

- `FetchedSchemaSource` pydantic record:
  `modelo_code: ModeloCode`, `boe_ref: str`,
  `origin_url: AnyHttpUrl`, `pdf_path: Path`,
  `sha256: str (regex)`, `content_length: int (ge=1)`,
  `fetched_at: AwareDatetime`.
- `BoeOrdenSource` — small frozen pydantic model
  `(modelo_code: ModeloCode, boe_ref: str, origin_url:
  AnyHttpUrl)`.
- `BOE_ORDEN_SOURCES: tuple[BoeOrdenSource, ...]` — the
  fetcher looks up a `(modelo_code, boe_ref)` pair against
  this table. Initial entries:
  - `(ModeloCode.MODELO_130, "BOE-A-2023-15412",
    "https://www.boe.es/boe/dias/2023/07/13/pdfs/BOE-A-2023-15412.pdf")`.
  Follow-up issues add 303 / 390 sources.
- `fetch_boe_pdf(modelo_code, boe_ref, *, settings, override_url=None)
  -> FetchedSchemaSource`:
  1. Resolve override from
     `settings.aeat_schema_source_urls_override` (JSON-decoded
     if non-empty) or the static table.
  2. Destination = `resolve_schema_cache_file(code, boe_ref,
     settings.aeat_schema_cache_dir).with_suffix(".pdf")`.
  3. Stream via `httpx.stream("GET", url,
     follow_redirects=True, timeout=60.0)` — identical pattern
     to `aeat.domain.manuals._fetch._stream_to_file`. Hash while
     streaming.
  4. Build and return `FetchedSchemaSource`.
  5. Wrap `httpx.HTTPError` as `SchemaCacheError`.
- Does NOT write a manifest JSON — the manifest is embedded in
  the `Modelo.provenance` block when the extractor runs
  subsequently.

`_cache.py`:

- `resolve_schema_cache_file(code, boe_ref, root) -> Path`:
  returns `root / f"modelo_{code.value}" / f"{boe_ref}.json"`.
  Sanitises `boe_ref` to match `^[A-Z0-9-]+$` or raises
  `SchemaCacheError`.
- `save_modelo_to_cache(modelo, root)`:
  writes `Modelo.model_dump_json(indent=2, by_alias=True)` with
  sorted keys (`model_dump` then `json.dumps(sort_keys=True)`).
  Mkdir parents.
- `load_modelo_from_cache(code, boe_ref, root) -> Modelo`:
  reads + validates JSON, wraps validation errors as
  `SchemaValidationError`.

## Step 5 — Extractor Protocol + BoeOrdenExtractor

`_extractor.py`:

```python
@typing.runtime_checkable
class Extractor(typing.Protocol):
    def extract(self) -> Modelo: ...
```

`_boe_extractor.py`:

- `BoeOrdenExtractor(source: FetchedSchemaSource, modelo_code:
  ModeloCode, period: str)` — single pydantic record carries
  every provenance scalar so the extractor does not re-hash.
  Matches the "no bare dicts / pydantic everywhere" shape.
  This is a tightening of ADR §3's constructor signature;
  recorded here (not ADR-breaking — ADR allowed "per-backend
  configuration"). The old scalar signature is not
  implemented.
- `extract(self) -> Modelo`:
  1. `with pdfplumber.open(self.pdf_path) as pdf: ...`.
  2. Locate annex start: scan each page's `extract_text()`
     output for a regex `r"^\s*ANEXO\s*I?\s*$"` or the phrase
     `"Aprobación del modelo"`. First match wins. Raise
     `SchemaExtractionError("annex not found in BOE ...")`
     otherwise.
  3. From the annex start to the end-of-document, call
     `page.extract_tables()`. For each row, classify:
     - **Heading row** (single-cell, bold-likely): starts a
       new block; remember the Spanish label.
     - **Casilla row**: first cell matches `^(\d{2,4})$`,
       second cell is the Spanish label.
     - **Formula row**: starts with `"Casilla"` or matches
       `_FORMULA_LINE_RE`; parse into a `FormulaNode` via
       `_parse_formula_prose(label, row_text)`.
  4. Build a list of `Casilla` objects (Spanish label only in
     v1; English/Hungarian intentionally absent — downstream
     translation is `aeat.domain.casillas`' concern).
  5. Detect each casilla's `data_type` heuristically:
     - Labels containing "Cuota", "Importe", "Base imponible",
       "Resultado" → `CURRENCY_EUR`.
     - Labels containing "%", "Tipo", "Porcentaje" →
       `PERCENTAGE`.
     - "Ejercicio" / "Año" → `INTEGER`.
     - Fallback → `CURRENCY_EUR` (the dominant type on tax
       forms).
  6. `required` defaults to `True` for casillas without
     formulas; `computed` mirrors `formula is not None`.
  7. Assemble `SchemaProvenance` from the constructor args and
     return a `Modelo`.

`_parse_formula_prose(label_text, trailing_text)`:

- Pattern `r"=\s*Casilla\s*(\d+)"` → `CasillaRef`.
- Pattern `r"=\s*Casilla\s*(\d+)\s*([-+×x*/])\s*Casilla\s*(\d+)"`
  → `BinaryOp`.
- Pattern `r"=\s*Casilla\s*(\d+)\s*×\s*0,(\d+)"` →
  `BinaryOp(MUL, CasillaRef(m), LiteralFormula(Decimal("0." + n)))`.
- Pattern `r"=\s*suma"` + repeated `r"Casilla\s*(\d+)"` →
  `SumFormula`.
- Fallback: raise `SchemaExtractionError` with the unparsed
  prose + page number. (v1 deliberately narrow — 130 uses
  only sums and two-term diffs.)

### Why this fidelity is enough for the PoC

Modelo 130 has ~20 casillas and only two formula shapes:
- `Casilla N = Casilla A + Casilla B - ...`  (sums / diffs)
- `Casilla N = Casilla A × 0,20` (quarterly advance at 20%)

Both fall within the pattern set above. The extractor is
deliberately not general-purpose — it is the reference
implementation that downstream 303/390 extractors will extend
via subclass + additional `_FORMULA_*_RE` patterns.

## Step 6 — settings additions

`src/aeat/config.py`:

- Add new section header comment
  `# ── Schema extraction (aeat.domain.schema, #9) ────────────────`.
- Add fields:
  ```python
  aeat_schema_cache_dir: Path = Field(
      default=PROJECT_ROOT / "var" / "schema-cache",
      description="Directory where extracted Modelo schemas...",
  )
  aeat_schema_source_urls_override: str = Field(
      default="",
      description="Optional JSON-encoded...",
  )
  aeat_schema_extraction_concurrency: int = Field(
      default=2,
      ge=1,
      description="Max parallel BOE PDF fetches during refresh",
  )
  ```
- Add **only** `aeat_schema_cache_dir` to the
  `_normalize_repo_relative_paths` validator list. The other two
  new fields are `str` and `int` respectively and MUST NOT be
  listed.

`env/.env.example`:

- Append section:
  ```
  # -- Schema extraction (aeat.domain.schema, #9) --------------------------------
  # Directory where extracted Modelo schemas and provenance manifests live.
  AEAT_SCHEMA_CACHE_DIR=var/schema-cache
  # Optional JSON-encoded {modelo_code: {boe_ref: url}} override for offline CI.
  AEAT_SCHEMA_SOURCE_URLS_OVERRIDE=
  # Max parallel BOE PDF fetches during refresh.
  AEAT_SCHEMA_EXTRACTION_CONCURRENCY=2
  ```

`tests/test_config.py` picks these up automatically via
`Settings.env_var_names()` and the env-example parser.

## Step 7 — CLI wiring

`src/aeat/entrypoints/cli/schema.py` (the file that owns the Typer app in the
final implementation; `aeat.domain.schema._cli` does not exist per the
plan's own §1 resolution):

- `app = typer.Typer(name="schema", help="Extract AEAT modelo
  schemas from authoritative sources.", no_args_is_help=True,
  add_completion=False)`.
- `refresh(...)`:
  - `--modelo` (required, Typer converts to `ModeloCode` via
    enum; or parses as str and calls `ModeloCode(value)`).
  - `--boe-ref` (required).
  - `--period` (required).
  - `--_pdf-path-override` (`hidden=True`, default `None`).
  - Body: resolve settings, if override is set use it else
    `fetch_boe_pdf(...)`, build `BoeOrdenExtractor`, run
    `.extract()`, write via `save_modelo_to_cache`, echo the
    target path.
- `show(...)`:
  - `--modelo`, `--boe-ref`.
  - Body: `load_modelo_from_cache(...)`, pretty-print JSON.

`src/aeat/entrypoints/cli/schema.py` — **authored in full** like
`src/aeat/entrypoints/cli/casillas.py`. It imports domain helpers only from
the public `aeat.domain.schema` surface (`fetch_boe_pdf`,
`BoeOrdenExtractor`, `save_modelo_to_cache`,
`load_modelo_from_cache`, `BOE_ORDEN_SOURCES`, error classes,
`ModeloCode` via `aeat.domain.modelos`). The package-internal
`aeat.domain.schema._cli` module referenced elsewhere in this plan is
renamed to **live in `aeat.entrypoints.cli.schema` directly** — there is no
`aeat.domain.schema._cli` module. This collapses the wiring to the
existing casillas precedent and preserves the "no underscore
imports" public-API discipline.

`src/aeat/entrypoints/cli/__init__.py`:

- Import: `from aeat.entrypoints.cli import schema as schema_module`.
- Register: `app.add_typer(schema_module.app, name="schema",
  help="Programmatic AEAT modelo schema extraction.")`.

## Step 8 — unit tests

All tests carry `@pytest.mark.unit`. Every test is hermetic —
no network, no authentication, no mocks.

### `test_models.py`

- `_build_valid_modelo_130()` fixture returns a hand-assembled
  `Modelo` (no extractor) used across tests.
- Happy path: construct one of each `FormulaNode` / `ValidationRule`
  variant, round-trip `model_dump_json` → `model_validate_json`,
  assert equality.
- `evaluate`:
  - literal → Decimal match.
  - ref → lookup.
  - binop ADD/SUB/MUL; DIV with quantisation; DIV by zero raises
    `SchemaExtractionError`.
  - sum of two refs.
- Validator negatives:
  - `Casilla(formula=..., computed=False)` → `ValidationError`.
  - `Modelo` with dangling casilla ref → `ValidationError`.
  - `Modelo(provenance.source=BOE_ORDEN)` with `Casilla.source_page=None`
    → `ValidationError`.
  - `Portal` whose `related_modelo` mismatches →
    `ValidationError` (imports `aeat.domain.portals` lazily inside
    the test via `aeat.domain.schema._models` — we test the validator,
    not `aeat.domain.portals`).
- `validate_period_for_modelo`:
  - `MODELO_130` + `"2025Q4"` passes.
  - `MODELO_130` + `"2025"` fails.
  - `MODELO_390` + `"2025"` passes.
  - `MODELO_390` + `"2025Q4"` fails.

### `test_boe_extractor.py`

- Top of file: a helper `build_fake_boe_pdf(path: Path) -> None`
  (imported from `aeat.domain.schema.testing`) that uses `reportlab`
  — same technique as `src/aeat/domain/justificante/test_parser.py`.
  The synthetic PDF contains:
  - Page 1: preamble text, then `"ANEXO I"`.
  - Page 2+: a table with five rows:
    1. `"Base imponible 1T"` — casilla 01, CURRENCY_EUR.
    2. `"Ingresos computables"` — casilla 03.
    3. `"Rendimiento neto"` — casilla 07 = `Casilla 01 - Casilla 03`.
    4. `"Pago fraccionado"` — casilla 13 = `Casilla 07 × 0,20`.
    5. A formula row: `"Casilla 07 = Casilla 01 - Casilla 03"`.
    6. A formula row: `"Casilla 13 = Casilla 07 × 0,20"`.
  - The layout is deliberately simplified but preserves the
    row shapes the extractor's regex library handles.
- Test `test_extract_modelo_130_from_fake_boe(tmp_path)`:
  - Build PDF into `tmp_path / "boe.pdf"`.
  - Assemble a `FetchedSchemaSource` from the real bytes and
    run `BoeOrdenExtractor(source=FetchedSchemaSource(...),
    modelo_code=MODELO_130, period="2025Q4")`.
  - Assert:
    - Returned `Modelo.modelo_code == MODELO_130`.
    - Four casillas: `{"01", "03", "07", "13"}`.
    - `casilla_07.formula` is a `BinaryOp(SUB,
      CasillaRef("01"), CasillaRef("03"))`.
    - `casilla_13.formula` evaluates to `Decimal("120.00")`
      when `values = {"07": Decimal("600.00")}`.
    - `provenance.source == SchemaSource.BOE_ORDEN`.
- Negative test: call extractor on a PDF without `"ANEXO"` —
  asserts `SchemaExtractionError("annex not found...")`.

### `test_cache.py`

- Round-trip: build a `Modelo`, `save_modelo_to_cache(tmp_path)`,
  `load_modelo_from_cache(...)`, assert deep equality via
  `model_dump`.
- Path shape: assert file ends with
  `modelo_130/BOE-A-2023-15412.json`.
- Malformed JSON on disk → `SchemaValidationError`.
- Dirty `boe_ref` (`"../etc/passwd"`) → `SchemaCacheError`.

### `test_cli.py`

- Typer `CliRunner`.
- `refresh --modelo MODELO_130 --boe-ref BOE-A-FAKE --period 2025Q4
  --_pdf-path-override <tmp_path/fake.pdf>` ends with exit code 0
  and writes the expected cache file.
- `show --modelo MODELO_130 --boe-ref BOE-A-FAKE` prints JSON
  that parses back into a `Modelo`.
- `refresh` through the real `fetch_boe_pdf` path: write the
  generated PDF to `tmp_path`, point
  `aeat_schema_source_urls_override` at `file:///<tmp_path>/
  boe.pdf` (httpx natively handles `file://`), run without
  the `--_pdf-path-override` flag, assert the cache file
  exists. **No mocking library is imported.**

### `test_smoke.py` (new content replaces current stub)

- `aeat.domain.schema.__doc__` present.
- Every name in `__all__` is actually importable.
- `aeat.domain.casillas` is NOT imported by any `aeat.domain.schema`
  submodule — enforced by AST-scanning every `.py` file under
  `src/aeat/domain/schema/` for `Import` / `ImportFrom` nodes whose
  module starts with `aeat.domain.casillas`. The scan mirrors the
  proven pattern in `tests/conftest.py` for banned-import
  enforcement. `sys.modules` inspection is NOT used (it is
  globally polluted by sibling tests).

### `tests/test_config.py`

No code changes needed — the existing shared assertion
`Settings.env_var_names() == _parse_env_example_vars()` picks
up the three new settings automatically once `.env.example`
is updated.

## Step 9 — verification loop

Execute in order:

1. `uv sync` (no-op if already synced; safety).
2. `uv run pytest src/aeat/schema -x -q` — fast feedback on
   the new subpackage's tests.
3. `uv run pytest tests/test_config.py -x -q` — env parity.
4. `uv run pytest -q` — full suite. Must stay green.
5. `uv run ruff check src/aeat/schema` — zero findings.
6. `uv run mypy src/aeat/schema` — zero errors. (Check
   whether the project uses pyright instead; if so use
   `just typecheck`.)
7. `just test-cov` — coverage for `src/aeat` stays ≥ 60%
   (new module adds coverage, never subtracts).

Any failure pauses execution and the issue is fixed
root-cause, never suppressed with `# type: ignore` /
`# noqa` unless the underlying platform is at fault
(extremely rare).

## Step 10 — commit + PR

- Single commit: `feat(schema): extract AEAT modelo schemas
  from BOE Ordenes (#9)`.
- PR body:
  - Links to `#9`, the research doc, the ADR, and this plan.
  - Summary of landed vs. deferred items (reads from ADR
    §Deferred).
  - Test checklist reproducing Step 9.
- `gh pr create` opens the PR against `main`.

## Out of scope (tracked for follow-up)

- BOE URL entries for 303 / 390.
- Extractor pattern extensions for 303's rate-table rows and
  390's quarterly-sum rows.
- `aeat schema diff` CLI.
- `aeat.domain.casillas` ↔ `aeat.domain.schema` adapter PR.
- Removal of the duplicate `aeat.domain.casillas.models.ModeloCode`.
- Live-portal probe (`SchemaSource.PORTAL_HTML_PROBE`).
- LLM-assisted validation rule extraction
  (`SchemaSource.MANUAL_LLM_DRAFT`).
- XSD wire-format extractor (`SchemaSource.XSD_WIRE`).

## Risk register

| Risk | Mitigation |
|------|-----------|
| `pdfplumber` behaviour differs between the synthetic reportlab PDF and a real BOE PDF. | The regex library is intentionally tolerant of whitespace and hyphen / minus-sign variants. A follow-up issue adds a live `@pytest.mark.live` probe that fetches the real BOE PDF. |
| Two `CasillaDataType` enums live briefly. | ADR §7 pins the string-value round-trip contract; `isinstance` cross-comparison is forbidden. Adapter PR removes the duplicate. |
| `typer` + `StrEnum` decoding quirk for `--modelo MODELO_130`. | Accept the raw string, call `ModeloCode(value_or_name_resolved)` with a helper that accepts both the value (`"130"`) and the member name (`"MODELO_130"`). |
| Mypy strict on pydantic discriminated unions. | Pattern proven in `aeat.domain.casillas`, `aeat.application.filing`, and `aeat.domain.justificante`; cross-check `model_rebuild()` order matches those modules. |
