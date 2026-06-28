---
tags:
  - "#plan"
  - "#aeat-history-fetch"
date: 2026-04-16
modified: '2026-04-16'
title: AEAT filing-history read surface — implementation plan
related:
  - "[[2026-04-16-aeat-history-fetch-adr]]"
  - "[[2026-04-16-aeat-history-fetch-research]]"
  - "[[2026-04-12-status-reader-adr]]"
  - "[[2026-04-12-notifications-inbox-adr]]"
issue: wgergely/aeat#168
epic: wgergely/aeat#166
status: approved
---

# aeat filing-history read surface — implementation plan

Implements the `aeat.history` subpackage per
`[[2026-04-16-aeat-history-fetch-adr]]`: a strictly-read-only
filing-history fetcher that, given the list of submitted `Expediente`
rows, retrieves the per-filing detail page, parses the casilla→value
mapping, and persists the result as strict pydantic v2 records.

## proposed changes

- New subpackage `src/aeat/history/` with:
  - `__init__.py` (public API re-exports only)
  - `_errors.py` (`HistoryError`, `HistoryFetchError`,
    `HistoryParseError`, `HistoryUnsupportedModeloError`)
  - `_models.py` (`FiledModeloMetadata`, `RawCalculationPayload`,
    `FiledModelo`, `FilingHistory`, `HistoryModelo` StrEnum)
  - `_protocols.py` (`ExpedienteSource`, `FilingDetailFetcher`,
    `CertificateBackend`, `RawExpediente` stub)
  - `_decimal.py` (Spanish-locale `parse_decimal` helper)
  - `_parsers/__init__.py` (registry + dispatch)
  - `_parsers/modelo_130.py`
  - `_parsers/modelo_303.py`
  - `_parsers/modelo_390.py`
  - `_fetcher.py` (`HistoryFetcher` async driver + persistence helpers)
  - `test_models.py`, `test_fetcher.py`, `test_decimal.py`,
    `test_errors.py`
  - `_parsers/test_modelo_130.py`, `_parsers/test_modelo_303.py`,
    `_parsers/test_modelo_390.py`
  - `test_live.py` (opt-in `@pytest.mark.live_read`)
- Three new fixtures under
  `tests/fixtures/aeat-pages/filing-history/`:
  - `modelo_130_detail.html`
  - `modelo_303_detail.html`
  - `modelo_390_detail.html`
- Three new settings fields in `src/aeat/config.py`:
  - `aeat_filing_history_dir: Path`
  - `aeat_filing_history_cache_ttl_s: int`
  - `aeat_filing_history_archive_html: bool`
- Two corresponding lines in `.env.example` + aligned
  `tests/test_config.py` coverage.
- One new grep gate test in `src/aeat/history/test_no_write_surface.py`
  that walks every `.py` under `src/aeat/history/` and asserts zero
  matches for the mutating-Playwright regex from the ADR D1 gate.
- Conventional-commit message throughout
  (`feat(history): ...`, scope = `history`).

## tasks

### phase 1 — scaffold + models

1. Create `src/aeat/history/__init__.py` with empty `__all__`
   (filled as each submodule lands).
2. Create `src/aeat/history/_errors.py` subclassing
   `..errors.AeatError`. Members:
   `HistoryError`, `HistoryFetchError`, `HistoryParseError`,
   `HistoryUnsupportedModeloError`.
3. Create `src/aeat/history/_models.py` with the strict+frozen
   `FiledModeloMetadata`, `RawCalculationPayload`, `FiledModelo`,
   `FilingHistory` pydantic models plus the `HistoryModelo` `StrEnum`
   (members: `MODELO_130`, `MODELO_303`, `MODELO_390`). Include
   `model_validator` invariants:
   - `FiledModeloMetadata.presented_at` must be tz-aware and not in
     the future.
   - `RawCalculationPayload.casillas` keys match `^[0-9A-Z]{2,8}$`
     (mirrors `_CASILLA_ID_RE` in `aeat.domain.casillas.models`) — use a
     pre-compiled regex local to `_models.py` to avoid the
     private-module cross-import ADR-D12 rule forbids.
   - `FilingHistory.entries` key must equal each record's
     `metadata.expediente_id`.
4. Create `src/aeat/history/_decimal.py` with a documented
   `parse_decimal` port of
   `aeat.domain.justificante._extract._parse_decimal`. Raises
   `HistoryParseError` on invalid input.
5. Write `src/aeat/history/test_models.py`: round-trip every model
   through `model_dump_json()` / `model_validate_json()`, verify
   `extra="forbid"`, verify invariants above raise `ValidationError`.
   Apply module-level `pytestmark = [pytest.mark.unit,
   pytest.mark.domain_aeat_remote, pytest.mark.domain_local_state]`
   (local-state marker reflects the persistence round-trip).
6. Write `src/aeat/history/test_decimal.py`: cover Spanish locale
   (`"1.234,56"`), English locale (`"1234.56"`), negative, zero,
   malformed → `HistoryParseError`.
   Apply module-level markers `[pytest.mark.unit,
   pytest.mark.domain_infra]`.
7. Write `src/aeat/history/test_errors.py`: verify each error
   subclasses `AeatError` and composes the expected chain.
   Markers `[pytest.mark.unit, pytest.mark.domain_infra]`.

### phase 2 — protocols + parsers

1. Create `src/aeat/history/_protocols.py` with:
   - `ExpedienteSource` (runtime-checkable Protocol, async
     `list_expedientes(*, modelo: str | None = None,
     period: str | None = None) -> tuple[Expediente, ...]`).
   - `FilingDetailFetcher` (runtime-checkable Protocol, async
     `fetch_detail_html(expediente: Expediente) -> tuple[str, AnyHttpUrl]`).
   - `CertificateBackend` (structural mirror of
     `aeat.status._protocols.CertificateBackend`; not imported).
   - Use `..status.Expediente` (public re-export — already allowed
     per the public-API rule).
2. Create `src/aeat/history/_parsers/__init__.py` with:
   - `PARSER_REGISTRY: Mapping[HistoryModelo, Callable[..., FiledModelo]]`
     binding each enum member to its parser callable.
   - `parse_filing_detail(modelo, raw_html, *, expediente, source_url,
     fetched_at) -> FiledModelo` that dispatches via the registry.
   - Raises `HistoryUnsupportedModeloError` with a clear supported-set
     message for anything outside the registry.
3. Create `src/aeat/history/_parsers/modelo_130.py`. Signature
   `parse_modelo_130_detail(raw_html, *, expediente, source_url,
   fetched_at) -> FiledModelo`. Uses `BeautifulSoup4` with
   `html.parser`. Selects casilla cells by label text; returns
   `RawCalculationPayload` with `casillas={"01": "...", "02": "..."}`
   etc. Extracts `total_a_ingresar` / `total_a_devolver` via labelled
   regex over the form body. Records non-fatal observations in
   `parse_warnings` (e.g. "no total_a_ingresar label found").
4. Create `src/aeat/history/_parsers/modelo_303.py` analogous to 130.
5. Create `src/aeat/history/_parsers/modelo_390.py` analogous to 130,
   acknowledging 390 is an annual summary — extracts
   `resultado_a_compensar` if present.
6. Commit fixture HTML for each modelo under
   `tests/fixtures/aeat-pages/filing-history/`. Each fixture is a
   hand-trimmed form echoing 8-15 casillas with sanitised values
   (NIF `X1234567L`, round amounts, stable placeholder URLs).
   `.gitattributes` declares `*.html eol=lf` under this directory.
7. Write `_parsers/test_modelo_130.py`, `_parsers/test_modelo_303.py`,
   `_parsers/test_modelo_390.py`. Each:
   - Loads its fixture via `Path(__file__).parent`.
   - Calls the parser with a stable `expediente` + `source_url` +
     `fetched_at`.
   - Asserts exact `metadata.*` + exact `calculations.casillas`
     mapping + the expected totals.
   - Asserts malformed HTML → `HistoryParseError`.
   Markers `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`.

### phase 3 — fetcher + persistence

1. Create `src/aeat/history/_fetcher.py` with `HistoryFetcher`. API:
   - `__init__(*, expediente_source, detail_fetcher, settings,
     history_file: Path | None = None)`.
   - `load_history() -> FilingHistory` — safe on missing file (returns
     empty).
   - `save_history(history: FilingHistory) -> None`.
   - `async fetch_for_modelo(modelo: HistoryModelo | str, *,
     year: int | None = None, use_cache: bool = True) ->
     tuple[FiledModelo, ...]` — accepts either the `HistoryModelo`
     StrEnum or a raw modelo string (`"130"`, `"303"`, `"390"`);
     normalises through a module-level helper
     `_coerce_modelo(raw) -> HistoryModelo` which raises
     `HistoryUnsupportedModeloError` on a miss. Lists
     expedientes via `ExpedienteSource`, then for each row fetches
     detail HTML via `FilingDetailFetcher`, parses via the registry,
     merges into `FilingHistory`, persists, returns the new/updated
     records.
   - `async fetch_filed_modelo(expediente: Expediente, *,
     use_cache: bool = True) -> FiledModelo` — single-row path.
   - Cache policy per ADR D8: serve from `FilingHistory` when
     `fetched_at` is within the TTL and `use_cache=True`.
   - No write-surface verbs on any public method.
2. Write `src/aeat/history/test_fetcher.py`:
   - Build a real Protocol-conforming `FakeExpedienteSource` (returns
     a hand-built `(Expediente, ...)` tuple) and a real
     Protocol-conforming `FakeDetailFetcher` (returns fixture HTML by
     `expediente_id`). Both are normal Python classes — no
     `unittest.mock`, no `pytest_mock`.
   - Cover: empty history on first call; idempotent second call;
     cache bypass with `use_cache=False`; unsupported modelo raises
     `HistoryUnsupportedModeloError`; persistence round-trips
     through `FilingHistory.model_validate_json`.
   - Run with `tmp_path` for `history_file`.
   Markers `[pytest.mark.unit, pytest.mark.domain_aeat_remote]`.
3. Add `src/aeat/history/test_no_write_surface.py`: walks every
   `.py` file under `src/aeat/history/` and asserts (via `re.search`)
   that the ADR D1 forbidden regex has zero matches. Asserts the
   public-API `__init__.py` exports zero names matching the
   write-verb regex. Markers `[pytest.mark.unit,
   pytest.mark.domain_infra]`.
4. Wire public API in `src/aeat/history/__init__.py`: export
   `HistoryFetcher`, `FilingHistory`, `FiledModelo`,
   `FiledModeloMetadata`, `RawCalculationPayload`, `HistoryModelo`,
   and every error class. Module docstring explains the read-only
   contract + non-goals verbatim from ADR D1/D10.

### phase 4 — config + live harness

1. Add to `src/aeat/config.py` (under a new
   `# ── Filing history (#168) ──` banner):
   - `aeat_filing_history_dir: Path = PROJECT_ROOT / "var" / "filing-history"`.
   - `aeat_filing_history_cache_ttl_s: int = 900`.
   - `aeat_filing_history_archive_html: bool = False` (controls the
     optional `pages/<expediente_id>.html` archive described in ADR
     D7).
   - `aeat_filing_history_dir` listed in the
     `_normalize_repo_relative_paths` validator's tuple.
2. Append matching lines to `.env.example`.
3. Update `tests/test_config.py` if needed (it auto-discovers from
   `Settings.env_var_names`; only add an explicit assert if the test
   expects a specific docstring).
4. Create `src/aeat/history/test_live.py` with a single
   `@pytest.mark.live_read` test that:
   - Skips (not drops) when `AEAT_LIVE_TESTS_ENABLED != "1"`.
   - When enabled, builds a real `HistoryFetcher` against the real
     status reader + browser session + certificate backend.
   - Asserts `fetch_for_modelo("130", year=2025)` returns a tuple
     (possibly empty).
   - Markers `[pytest.mark.live_read, pytest.mark.domain_aeat_remote]`.
   - Zero mocks, zero patches, zero fakes — per the live-test
     testing charter.

### phase 5 — verification + PR

1. Run `uv run pytest src/aeat/history/ -q` — all green.
2. Run `uv run pytest -q` — full suite green.
3. Run `just lint` — clean.
4. Run `just test-cov` — 60% floor preserved; new subpackage
   contributes additional coverage.
5. Run the ADR D1 grep gate manually as a second belt-and-braces
   check:
   `rg -n 'page\.(fill|click|type|select_option|check|press|set_input_files)|form\.submit|\.click\(\)' src/aeat/history/`
   — expect zero hits.
6. Stage conventional commits:
   - `feat(history): add read-only filing-history subpackage (#168)`.
   - `test(history): add per-modelo parser + fetcher unit tests (#168)`.
   - `docs(history): add vault research + adr + plan (#168)`.
   - `chore(config): expose filing-history paths + TTL in Settings (#168)`.
7. Push branch; open PR via `gh pr create` against `main`. PR body:
   - Links `#168` and `EPIC #166`.
   - Pastes a compact summary of ADR decisions (D1..D12).
   - Test plan: unit suite, live harness opt-in.
8. Code review by `vaultspec-code-reviewer`: block on write-surface,
   pydantic strict, relative imports, Protocol compliance.
9. Address review output.

## success criteria

- `uv run pytest src/aeat/history/` passes.
- `just lint && just typecheck` (if typecheck exists in the justfile)
  clean; ruff TID251 reports no banned imports in the new subpackage.
- `rg -n 'page\.(fill|click|type|select_option|check|press|set_input_files)|form\.submit|\.click\(\)' src/aeat/history/`
  returns zero hits.
- `rg -n 'from unittest|import mock|pytest_mock|pytest_httpx|time_machine|freezegun|vcr' src/aeat/history/`
  returns zero hits.
- `FilingHistory` round-trips through `model_dump_json()` and
  `model_validate_json()` without loss.
- Live-read harness skips (not errors) when
  `AEAT_LIVE_TESTS_ENABLED != "1"`.
- PR is opened, references `#168` and `EPIC #166`, and links the
  three vault documents.
