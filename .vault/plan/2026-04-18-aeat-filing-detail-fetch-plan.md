---
tags:
  - "#plan"
  - "#aeat-filing-detail-fetch"
date: 2026-04-18
modified: '2026-04-18'
title: Plan — StatusReader.fetch_filing_detail (#227)
status: ready
issue: wgergely/aeat#227
epic: wgergely/aeat#70
related:
  - "[[2026-04-18-aeat-filing-detail-fetch-adr]]"
  - "[[2026-04-18-aeat-filing-detail-fetch-research]]"
  - "[[2026-04-16-aeat-history-fetch-adr]]"
  - "[[2026-04-12-status-reader-adr]]"
---

# plan — StatusReader.fetch_filing_detail (#227)

## goal (Kent-observable)

> Kent's future `aeat revise` command can pull his previously-filed
> casilla values from AEAT for a given `(modelo, period)` without
> ever mutating AEAT state.

No CLI ships in this PR — the plan delivers the load-bearing read
surface on which amendment flows compose. The enforcement path runs
through strict+frozen pydantic records and an exhaustive unit test
suite.

## what this plan implements

- `aeat.status.StatusReader.list_expedientes(*, modelo, period,
  use_cache=True)` — Protocol-compatible thin wrapper.
- `aeat.status.StatusReader.fetch_detail_html(expediente)` —
  Protocol-compatible detail-page fetcher.
- `aeat.status.StatusReader.fetch_filing_detail(modelo, period, *,
  use_cache=True)` — the public composition facade.
- `aeat.status.Expediente.detail_url: AnyHttpUrl | None` — new
  additive schema field.
- `aeat.status._parsers.expedientes` — capture `detail_url` when
  AEAT renders an explicit detail anchor.
- `aeat.core.config.Settings.aeat_status_detail_url_template` — new env
  var, strict format validator.
- `env/.env.example` — document the new env var.
- Fixtures + unit tests for every new code path.

## non-goals

Inherited from `[[2026-04-18-aeat-filing-detail-fetch-adr]]` D10.
Explicitly excluded: CLI wiring; new modelo parsers; live-AEAT
integration tests; PDF justificante fallback; new persistence layer.

## phases and steps

### phase-1 — schema and config additions

**Step 1.1 — extend `aeat.status._models.Expediente`**

- Add `detail_url: AnyHttpUrl | None = None`.
- Leave `strict=True, frozen=True, extra="forbid"` unchanged.
- Location: `src/aeat/status/_models.py:54`.

**Step 1.2 — extend parser**

- File: `src/aeat/status/_parsers/expedientes.py`.
- Add `"detalle"` / `"acciones"` / `"acción"` (normalised) to the
  recognised detail-link columns.
- New helper: `_extract_detail_anchor(cells, columns, source_url_str) -> AnyHttpUrl | None`
  searches the above columns for an `<a href>` (absolutised via
  `urljoin`).
- Pass resulting URL to the `Expediente(...)` constructor.
- Backwards-compatible: rows without such a column yield `None`.
- Update unit tests in `_parsers/test_expedientes.py` to cover
  both the populated and absent cases.

**Step 1.3 — fixture refresh**

- Extend `tests/fixtures/aeat-pages/expedientes/sample_spanish.html`
  (and `sample.html`) to include a "Detalle" column with a clear
  `<a href>` on at least one row and no anchor on another row. Do
  not alter the existing header shape beyond adding the new column.
  Regenerate as a new fixture
  (`tests/fixtures/aeat-pages/expedientes/sample_with_detail.html`)
  if additive extension would disrupt existing parser tests; the
  original fixture stays untouched for existing regression coverage.

**Step 1.4 — settings**

- File: `src/aeat/config.py`.
- New field under the existing `# ── Status reader (#43) ──` block
  (approx. line 504, immediately after
  `aeat_status_browser_trace_dir`):

```python
aeat_status_detail_url_template: str = Field(
    default="/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}",
    description=(
        "URL path template for an expediente detail page. "
        "Must contain '{expediente_id}'. Overrideable per campaign."
    ),
)
```

- Add a `@field_validator("aeat_status_detail_url_template")` using
  the **default mode** (`mode="after"`) so strict-typed input is
  already coerced to `str`, matching the existing validators around
  `config.py:584`. Reject values that do not contain the exact
  substring `"{expediente_id}"`.
- **Do NOT add this field to the `_normalize_repo_relative_paths`
  validator list** (`config.py:584-610`). The field is a URL-path
  *template string*, not a filesystem path — path normalisation
  would corrupt it.
- Mirror the format check in `tests/test_config.py` (top-level
  tests directory, NOT `src/aeat/test_config.py` — the project
  keeps config tests at `tests/test_config.py`).

**Step 1.5 — env example**

- File: `env/.env.example`.
- Append under "Status reader" block:

```
# URL path template for per-expediente detail pages. Must contain
# '{expediente_id}'. Override if AEAT changes the URL shape.
AEAT_STATUS_DETAIL_URL_TEMPLATE=/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}
```

### phase-2 — reader surface

**Step 2.1 — module-level constants and imports in `_reader.py`**

- Add to the existing `from urllib.parse import urljoin` line:
  `from urllib.parse import quote, urljoin` (add `quote`).
- Add near the top, beside `_EXPEDIENTES_PATH`:

```python
_EXPEDIENTE_DETAIL_PATH_TEMPLATE_DEFAULT = (
    "/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}"
)
```

- Use the Settings value when set; fall back to the module constant
  if the Settings override is blank (should not happen with the
  default but defends against explicit empty-string overrides).
- Reuse the existing module-level `_URL_ADAPTER: TypeAdapter[AnyHttpUrl]`
  at `_reader.py:47` — no second adapter.
- **Do NOT add a top-level `from ..history import ...`.** The
  `HistoryFetcher` import stays function-scoped inside
  `fetch_filing_detail` per ADR D5 (forward-design guard against
  `__init__` reorder-induced partial-init ImportError). A top-level
  comment in the method body re-states this rule for future
  contributors.

**Step 2.2 — `list_expedientes` method**

```python
async def list_expedientes(
    self,
    *,
    modelo: str | None = None,
    period: str | None = None,
    use_cache: bool = True,
) -> tuple[Expediente, ...]:
    records = await self.fetch_expedientes(use_cache=use_cache)
    if modelo is None and period is None:
        return records
    return tuple(
        r for r in records
        if (modelo is None or r.modelo == modelo)
        and (period is None or r.period == period)
    )
```

- Add docstring noting Protocol conformance with
  `aeat.history.ExpedienteSource`.

**Step 2.3 — `fetch_detail_html` method (new private `_build_detail_url` helper)**

```python
def _build_detail_url(self, expediente: Expediente) -> AnyHttpUrl:
    if expediente.detail_url is not None:
        return expediente.detail_url
    template = (
        self._settings.aeat_status_detail_url_template
        or _EXPEDIENTE_DETAIL_PATH_TEMPLATE_DEFAULT
    )
    # Validator enforced {expediente_id} presence at Settings load.
    path = template.format(
        expediente_id=quote(expediente.expediente_id, safe=""),
    )
    absolute = urljoin(self._settings.aeat_base_url, path)
    return _URL_ADAPTER.validate_python(absolute)

async def fetch_detail_html(
    self,
    expediente: Expediente,
) -> tuple[str, AnyHttpUrl]:
    page = await self._ensure_ready()
    url = self._build_detail_url(expediente)
    try:
        response = await page.goto(
            str(url),
            wait_until="domcontentloaded",
        )
    except Exception as exc:
        raise StatusReaderError(
            f"detail navigation failed for "
            f"expediente {expediente.expediente_id!r}: {exc}"
        ) from exc
    if response is not None and response.status >= 400:
        raise StatusReaderError(
            f"AEAT returned HTTP {response.status} for detail page "
            f"of expediente {expediente.expediente_id!r}"
        )
    html = await page.content()
    if not html:
        raise StatusReaderError(
            f"AEAT returned empty detail page for "
            f"expediente {expediente.expediente_id!r}"
        )
    return html, url
```

- Uses `urllib.parse.quote` to make the `{expediente_id}`
  substitution URL-safe.
- Explicitly refuses empty body (per ADR D8 enforcement checklist).
- No `page.fill/click/submit`, no form interaction.

**Step 2.4 — `fetch_filing_detail` method**

```python
async def fetch_filing_detail(
    self,
    modelo: str,
    period: str,
    *,
    use_cache: bool = True,
) -> tuple[FiledModelo, ...]:
    # Function-scoped import: forward-design guard against a
    # partial-init ImportError under future `aeat.status.__init__`
    # reordering. See ADR D5.
    from ..history import HistoryFetcher

    fetcher = HistoryFetcher(
        expediente_source=self,
        detail_fetcher=self,
        settings=self._settings,
    )
    return await fetcher.fetch_for_modelo(
        modelo,
        period=period,
        use_cache=use_cache,
    )
```

- Full docstring lists every raised error (ADR D8).
- TYPE_CHECKING import of `FiledModelo` (for the return-type
  annotation only) sits at the top of the file; the runtime
  `HistoryFetcher` import stays function-scoped.

**Step 2.5 — public API update**

- File: `src/aeat/status/__init__.py`.
- No new re-export needed (`FiledModelo` remains owned by
  `aeat.history`; consumers import it from there).
- Update the module docstring to mention `fetch_filing_detail` and
  the Protocol-conformance roles.

### phase-3 — tests

**Step 3.1 — unit tests for `Expediente.detail_url`**

- File: `src/aeat/status/test_models.py` (extend existing test class).
- Cover: populated URL round-trip, `None` default, invalid URL
  rejection, `extra="forbid"` preserved.

**Step 3.2 — unit tests for parser `detail_url` capture**

- File: `src/aeat/status/_parsers/test_expedientes.py`.
- Cases: row with detail anchor populates `detail_url`; row without
  detail column → `None`; multiple rows with mixed presence.

**Step 3.3 — unit tests for Settings**

- Colocated with existing config tests (find them first).
- Default value, override round-trip, format-validator rejection
  when `{expediente_id}` missing.

**Step 3.4 — unit tests for `list_expedientes`**

- File: `src/aeat/status/test_reader.py` (extend).
- Cases: no filter (identity), modelo-only, period-only, both,
  empty result. Assert single underlying `fetch_expedientes`
  invocation (cache hit + post-filter).

**Step 3.5 — unit tests for `fetch_detail_html`**

- Extend `test_reader.py` with a URL-keyed fake page. Approach:
  introduce `_FakeUrlKeyedPage` (or similar) that subclasses /
  mirrors the existing `_FakePage` contract **exactly** — the
  `.visited: list[str]` attribute is preserved, `goto` still
  records every navigated URL in order, and `content()` still
  returns the body. The only enhancement is that `content()` looks
  up the most recently visited URL in a `dict[str, str]` map. The
  existing tests at `test_reader.py:132, 151-155, 167-170` rely on
  `visited` list semantics; any change MUST leave those tests
  passing unchanged. Prefer composition (new class alongside
  `_FakePage`) over mutation of the existing class so regression
  risk is zero.
- Cases:
  - Populated `detail_url` used verbatim.
  - Absent `detail_url` → templated fallback.
  - Settings override applied.
  - HTTP ≥ 400 → `StatusReaderError`.
  - Empty body → `StatusReaderError`.
  - Uses `quote(expediente_id)` for URL-safe substitution.

**Step 3.6 — unit tests for `fetch_filing_detail`**

- Extend `test_reader.py` with end-to-end composition tests.
- Fixtures: reuse
  `tests/fixtures/aeat-pages/filing-history/modelo_130_detail.html`
  and `modelo_303_detail.html`.
- Cases:
  - Happy path: list → detail → parse → `FiledModelo` returned.
  - Modelo filter + period filter both applied (only matching
    expedientes expanded).
  - `HistoryUnsupportedModeloError` raised on unsupported modelo.
  - Cache hit path does not re-navigate on the second call.
  - `use_cache=False` forces re-fetch.
  - `isinstance(reader, ExpedienteSource)` and
    `isinstance(reader, FilingDetailFetcher)` both assert True.

**Step 3.7 — Playwright type-fidelity check**

- File: `src/aeat/status/test_reader.py`.
- New `_FakePage.goto` must preserve the existing response-shape
  contract (carries `.status`). Mirror the in-place shape without
  adding new behaviours. This prevents drift between test doubles
  and the real Playwright API.

**Step 3.8 — no-write-surface assertion test**

- File: `src/aeat/status/test_no_write_surface.py` (new).
- Mirrors `src/aeat/history/test_no_write_surface.py` verbatim,
  adjusted for `_HISTORY_ROOT` → `_STATUS_ROOT` and the public-API
  source (`from . import __all__ as status_public_api`).
- **Preserve the self-exclusion clause** (history copy lines 50–52):
  `if path.name == "test_no_write_surface.py": continue` — without
  it, the regex literal inside this file matches itself.
- Scans the `src/aeat/status/` tree and asserts:
  - Zero matches for `rg` pattern
    `page\.(fill|click|type|select_option|check|press|set_input_files)|form\.submit|\.click\(\)`.
  - No public API name (from `__all__`) matches
    `/(submit|send|ack|acknowledge|mark_|confirm|file_|post_)/i`.

### phase-4 — docs, hygiene, and dev loop

**Step 4.1 — ROADMAP and coverage matrices**

- `docs/coverage/kent-capabilities.md`: tick the "fetch previously-
  filed casilla values" row against wall 23.
- `docs/coverage/pipeline.md`: reflect the new read surface in the
  AEAT-remote column for modelo 130/303/390.
- `ROADMAP.md`: only if a 227-named entry exists; do not
  editorialise.

**Step 4.2 — dev loop**

- `just lint` — ruff + mypy clean.
- `just test` — pass (unit markers).
- `just test-cov` — the status subpackage coverage floor remains
  ≥ 60 %.
- `uv run vaultspec-core install --force` — regenerate rule
  artefacts if any vaultspec custom rule changed (none in this PR).

### phase-5 — code review

Load the `vaultspec-code-reviewer` persona via
`vaultspec-code-review` skill. Verify against the ADR enforcement
checklist **and** the AEAT project mandates:

- Read-only across all new code (`rg` sweep).
- Strict+frozen pydantic on every new boundary type.
- Relative imports inside `src/aeat/`.
- No mocks / fakes / stubs in live tests.
- Pydantic-v2 field validator on the template.
- Explicit error-taxonomy propagation (ADR D8).

### phase-6 — PR

- Branch already exists: `feature/227-status-reader`.
- Conventional-commit shape: `feat(status): fetch_filing_detail read surface (#227)`.
- PR body lists all ADR/plan/research artefact paths and the
  enforcement checklist.
- PR closes #227.
- Wait for automated reviewer feedback; action and iterate.

## files touched (summary)

| file | change |
|---|---|
| `src/aeat/status/_models.py` | +`Expediente.detail_url` field |
| `src/aeat/status/_parsers/expedientes.py` | capture detail anchor |
| `src/aeat/status/_parsers/test_expedientes.py` | tests for detail capture |
| `src/aeat/status/_reader.py` | +3 new methods, +helper, +constants |
| `src/aeat/status/test_reader.py` | tests for new methods |
| `src/aeat/status/test_models.py` | tests for new field |
| `src/aeat/status/test_no_write_surface.py` | **new** write-surface guardrail |
| `src/aeat/status/__init__.py` | docstring update (no new exports) |
| `src/aeat/config.py` | +Settings field + validator |
| `env/.env.example` | document new env var |
| `tests/fixtures/aeat-pages/expedientes/*.html` | extend / add fixture |
| `docs/coverage/*.md` | reflect capability delivered |
| `.vault/exec/2026-04-18-aeat-filing-detail-fetch/...` | execution records |

## acceptance (Kent-observable)

1. `uv run pytest src/aeat/status/ src/aeat/history/` passes.
2. `uv run mypy src/aeat/status` clean.
3. `uv run ruff check src/aeat/status` clean.
4. `StatusReader` passes `isinstance(reader, ExpedienteSource)` AND
   `isinstance(reader, FilingDetailFetcher)` at runtime.
5. `uv run pytest src/aeat/status/test_no_write_surface.py -q`
   passes.
6. The `fetch_filing_detail` docstring enumerates every raised
   error.
7. A review-script `rg -n
   'page\.(fill|click|type|select_option|check|press|set_input_files)|form\.submit|\.click\(\)'
   src/aeat/` returns zero matches.

## risks and mitigations (plan-level)

- **Existing `test_reader.py` fixture shape drift.** The fixture
  extensions for detail anchors may fail existing tests. Mitigation:
  add a parallel fixture (`sample_with_detail.html`) rather than
  edit the current ones; update only `test_expedientes.py` to use
  the new fixture in the relevant tests.
- **Circular-import regression.** If a future contributor moves
  `from ..history import HistoryFetcher` to the module top, module
  load breaks. Mitigation: ADR enforcement checklist; colocated
  comment in the method body.
- **`AnyHttpUrl` URL-validator drift.** `_URL_ADAPTER` validation
  on the joined URL enforces the shape. Cover with an invalid-
  template unit test.
- **Coverage regression.** Adding methods without tests would drop
  coverage; plan ships unit tests alongside each new code path.
