---
tags:
  - "#adr"
  - "#aeat-filing-detail-fetch"
date: 2026-04-18
modified: '2026-04-18'
title: ADR — StatusReader.fetch_filing_detail (#227)
status: accepted
issue: wgergely/aeat#227
epic: wgergely/aeat#70
related:
  - "[[2026-04-18-aeat-filing-detail-fetch-research]]"
  - "[[2026-04-12-status-reader-adr]]"
  - "[[2026-04-16-aeat-history-fetch-adr]]"
---

# adr — StatusReader.fetch_filing_detail (#227)

## context

Wall 23 of the Kent-revise audit names the missing dependency for
every retroactive amendment use case: a surface that fetches
previously-filed casilla values from AEAT. Issue #227 closes that
wall with a single public method on the existing
`aeat.status.StatusReader`:
`fetch_filing_detail(modelo, period) -> tuple[FiledModelo, ...]`.

The supporting infrastructure is already on main:

- `aeat.status.StatusReader` (#43) drives an authenticated Playwright
  browser and lists expedientes.
- `aeat.history.HistoryFetcher` (#168/#195) composes a per-filing
  detail-page fetcher + the per-modelo parser registry and persists
  typed records to disk.

The gap is the live driver that (a) filters expedientes by
`(modelo, period)` and (b) navigates each expediente's detail HTML
page. #227 binds these into one ergonomic entrypoint on
`StatusReader`.

See `[[2026-04-18-aeat-filing-detail-fetch-research]]` for the
architectural option analysis. This ADR pins the decisions.

## decisions

### D1 — read-only, zero write intent (non-negotiable)

`fetch_filing_detail` and every helper it reaches MUST be read-only
against AEAT. Every browser interaction is a
`page.goto(url, wait_until="domcontentloaded")` followed by
`page.content()`. No POSTs, no form submission, no
`page.fill/click/type/select_option/check/press/set_input_files`,
no `form.submit`, no write-intent public method names (regex
`/(submit|send|ack|acknowledge|mark_|confirm|file_|post_)/i`).

**Rationale:** the live-AEAT-write safety charter (#116) is
non-negotiable — AEAT has no sandbox; every write is legally
binding. This ADR inherits #168 D1 verbatim; enforcement is
mechanical:

1. `rg -n 'page\.(fill|click|type|select_option|check|press|set_input_files)|form\.submit|\.click\(\)' src/aeat/status/` → zero matches in the new code.
2. No public method added by this ADR matches the write-intent
   regex above.
3. Every new `page.goto(...)` call is recorded in the code-review
   checklist with its target URL and a justification line.

### D2 — StatusReader implements both Protocols structurally

`StatusReader` gains two structural roles, matching the existing
Protocols in `aeat.history._protocols` **without subclassing**:

- `ExpedienteSource` — via a new
  `async list_expedientes(*, modelo: str | None = None,
  period: str | None = None, use_cache: bool = True) ->
  tuple[Expediente, ...]`. Internally delegates to
  `fetch_expedientes` and applies the modelo/period filter.
- `FilingDetailFetcher` — via a new
  `async fetch_detail_html(expediente: Expediente) ->
  tuple[str, AnyHttpUrl]`. Internally navigates to the detail URL
  and returns `(html, resolved_url)`.

**Rationale:** the Protocols are `@runtime_checkable` and structural.
Making `StatusReader` conform by shape avoids a base-class import and
keeps the import DAG one-directional
(`aeat.history` → `aeat.status`). The method names match the Protocol
spellings exactly so a caller can pass `self` as both collaborators
to `HistoryFetcher` without adapter shims.

Enforcement: a unit test uses
`isinstance(reader, ExpedienteSource)` and
`isinstance(reader, FilingDetailFetcher)` — both Protocols are
`@runtime_checkable`, so the assertions fail fast when drift is
introduced.

**Signature superset note.** `StatusReader.list_expedientes` accepts
an additional `use_cache: bool = True` keyword argument beyond what
the #168 `ExpedienteSource` Protocol declares. This is a
*structural superset*: the extra kwarg has a default so the method
remains callable with the Protocol's exact signature. The #168
Protocol MUST NOT be tightened to include `use_cache` — that would
couple the Protocol to a `StatusReader`-local concern. Conversely,
stripping `use_cache` from the concrete method would lose the
freshness override. The superset relationship is intentional and is
a contract both subpackages rely on.

### D3 — fetch_filing_detail is a composition facade

`StatusReader.fetch_filing_detail(modelo, period, *, use_cache=True)`
is the only new public method visible to callers outside
`aeat.status`. It composes `HistoryFetcher.fetch_for_modelo` by
constructing the fetcher with `self` as both collaborators.

```python
async def fetch_filing_detail(
    self,
    modelo: str,
    period: str,
    *,
    use_cache: bool = True,
) -> tuple[FiledModelo, ...]:
    # Function-scoped import breaks the static cycle
    # between aeat.status and aeat.history.
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

**Rationale:** a single public facade matches the #227 title, hides
the two-Protocol plumbing from consumers, and reuses the full
`HistoryFetcher` cache / persistence / parser-registry machinery
untouched.

Both `modelo` and `period` are required positional-or-keyword
arguments. A naked `fetch_filing_detail()` would be unbounded; the
audit-driven use case is amendment flow (Kent knows which return he
is amending), which always knows the `(modelo, period)` pair.

### D4 — return type reuses `FiledModelo`; no new boundary type

The method returns `tuple[aeat.history.FiledModelo, ...]`. No new
pydantic model is introduced by this ADR. `FiledModelo` already
carries:

- strict+frozen config (#168 D4),
- full casilla payload (`dict[str, str]`, #168 D3),
- `complementaria_of` lineage (critical for amendment flows),
- `parse_warnings` for rejected / in-tramitación filings
  (#168 D11).

**Rationale:** minimising the boundary surface is a project mandate
(pydantic v2, strict). Introducing a parallel `FilingDetail` type
would fork the verification engine's inputs and duplicate validation
logic. The downstream local-state / verification layers already
consume `FiledModelo`; this method plugs directly into them.

### D5 — reverse import kept function-scoped (forward-design guard)

`aeat.history._protocols` imports `Expediente` from `aeat.status` at
module load. The reverse dependency (`aeat.status` →
`aeat.history`) needed for `HistoryFetcher` composition is
**function-scoped** inside `fetch_filing_detail` — it executes only
at first call, well after module load completes.

**Rationale.** Under the *current* `aeat.status.__init__` order
(`._models.Expediente` imported before `._reader`), a top-level
`from ..history import HistoryFetcher` inside `_reader.py` would
*probably* resolve, because `Expediente` is already bound on the
partial `aeat.status` module by the time the reverse chain asks for
it. But correctness then depends on `__init__` ordering — a fragile
implicit contract. Re-ordering imports for alphabetisation, or
adding an earlier top-level history import, would surface as a
partial-init `ImportError` at runtime.

Function-scoped imports sidestep that trap entirely. They are the
canonical cycle-breaker used elsewhere in the project (e.g. the
`SiteHealthAlert.stage → aeat.application.workflow.WorkflowStage` forward
reference documented at `aeat.status.__init__:55`).

Enforcement: top-level `from ..history import …` in
**production** modules under `src/aeat/status/` stays forbidden.
Test files (`test_*.py`) under the same tree may import from
`aeat.history` at module top because pytest only loads test
modules *after* the package finishes initialising — the
partial-init trap cannot fire there. The review sweep greps for
`^from \.\.history` and `^import .*history` in every non-`test_*`
Python file under `src/aeat/status/`.

### D6 — detail URL discovery: parser field first, template fallback

**Template provenance note.** The default template string
`"/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}"` is
**provisional** and documented as such in both this ADR and the
code comment on `_EXPEDIENTE_DETAIL_PATH_TEMPLATE`. It was inferred
from AEAT public-portal URL shapes observed in the wild (see the
research doc's "portal surface" section) but has not yet been
verified against a live authenticated session, because the cert
backend (#8) live bring-up is still in stabilisation. The
`AEAT_STATUS_DETAIL_URL_TEMPLATE` Settings override is the escape
hatch; a follow-up task (after #8 completion) MUST revalidate the
default against live AEAT and update it if necessary. The parser-
first path (`Expediente.detail_url`) is the authoritative source
whenever AEAT renders the link.


The detail URL for a given `Expediente` resolves in order:

1. **`Expediente.detail_url: AnyHttpUrl | None`** — added to the
   `_models.Expediente` schema (default `None`) and populated by
   `parse_expedientes` when an `Acciones` / `Detalle` column anchor
   is present in the row.
2. **Templated fallback** — when `detail_url is None`, construct via
   `urljoin(aeat_base_url,
   _EXPEDIENTE_DETAIL_PATH_TEMPLATE.format(
       expediente_id=quote(expediente_id, safe='')))`.
   Default template:
   `"/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}"`.
   Declared as a module-level constant in `_reader.py` and
   overrideable via a new Settings field
   `aeat_status_detail_url_template` (env
   `AEAT_STATUS_DETAIL_URL_TEMPLATE`) for operators running against a
   non-default AEAT campaign year.
3. **`justificante_url` is NOT a fallback.** The justificante is a
   signed PDF receipt without a casilla table; using it here would
   return PDF bytes that the history parsers cannot consume.

**Rationale:** the parser-first path is authoritative (AEAT is the
ground truth). The template fallback is the pragmatic bridge for
offline / older-fixture paths and the escape hatch if AEAT changes
the template. The `AnyHttpUrl | None` schema addition is
backwards-compatible.

The field addition preserves strict+frozen config and is validated by
pydantic. Unit-test fixtures are extended to cover both the
detail_url-populated and detail_url-absent rows.

### D7 — caching reuses HistoryFetcher (TTL + disk persistence)

The new method does **not** introduce its own cache. `HistoryFetcher`
already handles:

- TTL-gated lookup via `aeat_filing_history_cache_ttl_s`.
- `use_cache: bool = True` override (#168 D8).
- Persistence at `AEAT_FILING_HISTORY_DIR/history.json`.
- Optional raw-HTML archive via
  `AEAT_FILING_HISTORY_ARCHIVE_HTML=1`.

`StatusReader.fetch_filing_detail` forwards `use_cache` as-is.

The status reader's own `StatusCache` (#43) remains the cache for
the **listing** (`fetch_expedientes`). The detail-page cache lives
in `aeat.history` and continues to be owned there. This preserves
the single-responsibility boundary the #168 ADR established.

**Rationale:** no double-cache complexity, no duplicated TTL config,
no write-after-close races between two persistence layers. If
downstream needs finer-grained freshness control, it passes
`use_cache=False`.

### D8 — error taxonomy: re-raise, don't reclassify

`fetch_filing_detail` propagates the existing error classes
unchanged. No new error class is introduced. The union set of
errors the method may raise is:

- `StatusAuthError` — raised by the existing `_fetch_html` helper
  when the authenticated context cannot be prepared **or** when the
  *listing* navigation returns HTTP ≥ 400 (auth-session level).
- `StatusParseError` — raised by `parse_expedientes` on a malformed
  listing page or by `_fetch_detail_html` when the constructed /
  resolved detail URL fails pydantic `AnyHttpUrl` validation.
- `StatusReaderError` (base) — generic status-reader-level failure;
  in particular, `_fetch_detail_html` raises this when the detail
  navigation returns HTTP ≥ 400 (e.g. a 404 on a stale expediente,
  or a redirect-to-login that surfaces as HTTP 4xx/5xx). The message
  MUST carry the `expediente_id` and the HTTP status for diagnosis.
- `HistoryFetchError` — re-raised by `HistoryFetcher` if either
  collaborator raises unexpectedly (status errors get wrapped when
  they escape the generic `except Exception` in
  `_resolve_expediente`).
- `HistoryParseError` — raised by the per-modelo parser on a
  malformed detail page.
- `HistoryUnsupportedModeloError` — raised by `coerce_modelo` when
  the `modelo` string has no registered parser.

Mapping specifics:

- **404 / 5xx on the detail page** → `StatusReaderError` at the
  reader boundary, wrapped into `HistoryFetchError` by
  `HistoryFetcher._resolve_expediente` before it reaches the caller.
  The caller therefore sees `HistoryFetchError` whose
  `__cause__` is the original `StatusReaderError`.
- **Empty body on the detail page** → `StatusReaderError` at the
  reader boundary (we refuse to pass an empty string to the parser;
  parsers have a right to assume a non-empty input). Same wrapping
  flow as above.
- **Login-redirect detected on the detail navigation** → surface as
  `StatusAuthError` (auth-session has expired). This surfaces
  through `HistoryFetchError` by the same wrapping.

Every error on the path is a subclass of `aeat.core.errors.AeatError`,
so consumers can catch the base class for coarse handling or the
specific subclass for diagnostic routing.

**Rationale:** no value in hiding history-layer errors behind a
wrapper — callers that care about the distinction already have
access to both taxonomies. Hiding them would swallow diagnostic
signal for no architectural benefit. The mapping is explicit above
so future contributors don't silently change what a 404 means.

### D9 — no new Settings surface beyond the template override

This ADR adds exactly one new Settings field:

```python
aeat_status_detail_url_template: str = Field(
    default="/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}",
    description=(
        "URL path template for an expediente detail page. "
        "Must contain '{expediente_id}'. Overrideable per campaign."
    ),
)
```

Documented in `.env.example`. No other env var, no additional cache
TTL, no additional path.

**Rationale:** project mandate — every env var declared in
`Settings`. Minimises operational surface.

### D10 — non-goals are explicit

The method does NOT:

- Submit, amend, or file anything.
- Fetch justificante PDFs (that surface is #44's).
- Coerce casilla values (that is the verification engine's job, per
  #168 D3).
- Introduce a new persistence format — the `history.json` file is
  authoritative.
- Expand modelo coverage beyond what `aeat.history._parsers`
  supports today (130 / 303 / 390). Unsupported modelos raise
  `HistoryUnsupportedModeloError`.
- Ship a CLI entrypoint. CLI wiring is a follow-up once the live
  path is bring-up-ready (post #8 cert-backend completion).
- Add live tests that actually hit AEAT. Live tests remain
  opt-in-only (`pytest.mark.live_read`,
  `AEAT_LIVE_TESTS_ENABLED=1`) and parallel to the existing
  `test_live.py` placeholder.

## consequences

- Kent's amendment flow gains the load-bearing read surface
  (#227 closed, wall 23 closed).
- Wall 11 (live filing-history retrieval) and walls 21–22 (amendment
  import / justificante fallback) become composable off a single
  entrypoint.
- `StatusReader` grows two Protocol-conforming methods that are
  independently reusable (listing-filter, detail-fetch) even without
  going through `fetch_filing_detail`.
- `aeat.history.HistoryFetcher` now has a first-class live
  producer; no further change to `aeat.history` is required.
- `Expediente.detail_url` field is additive and
  backwards-compatible (default `None`). No on-disk JSON migration
  is required: `aeat.history` persists `FilingHistory` (which
  embeds `FiledModeloMetadata`, *not* `Expediente`) and the
  status-reader `StatusCache` revalidates on read, so a
  previously-cached listing missing `detail_url` is treated as a
  cache miss and re-fetched — the `extra="forbid"` strictness on
  `Expediente` does not break existing history data because no
  history data contains `Expediente` rows.
- One new Settings field + env var
  (`aeat_status_detail_url_template` /
  `AEAT_STATUS_DETAIL_URL_TEMPLATE`) documented in `.env.example`.
- Follow-ups: CLI wiring; expanding modelo coverage beyond 130/303/390;
  end-to-end live test against the real portal (gated on #8 completion);
  revalidate the default detail-URL template against live AEAT
  post-#8.

## enforcement / review checklist

- [ ] `rg -n 'page\.(fill|click|type|select_option|check|press|set_input_files)|form\.submit|\.click\(\)' src/aeat/status/` returns zero hits in new code.
- [ ] No public method added to `aeat.status` matches `/(submit|send|ack|acknowledge|mark_|confirm|file_|post_)/i`.
- [ ] `StatusReader` is a structural `ExpedienteSource` and
  `FilingDetailFetcher` (runtime `isinstance` asserts in tests).
- [ ] Top-level `from ..history import …` absent inside
  `src/aeat/status/`.
- [ ] New `Expediente.detail_url` is `AnyHttpUrl | None` with default
  `None`; strict+frozen config preserved.
- [ ] Unit tests use real Protocol-conforming classes (no mocks, no
  `unittest.mock`, no patches, no `pytest_mock`).
- [ ] Settings field `aeat_status_detail_url_template` + env var
  `AEAT_STATUS_DETAIL_URL_TEMPLATE` documented in `.env.example`.
- [ ] Module-level constant `_EXPEDIENTE_DETAIL_PATH_TEMPLATE` is the
  single source of the default template string.
- [ ] Test-fixture parity: at least one expediente row with
  `detail_url` populated and one relying on the template fallback.
- [ ] Unsupported modelo raises `HistoryUnsupportedModeloError` (not
  a new opaque error class).
- [ ] `fetch_filing_detail`'s docstring lists the full union of
  raised errors enumerated in D8 (StatusAuthError, StatusParseError,
  StatusReaderError, HistoryFetchError, HistoryParseError,
  HistoryUnsupportedModeloError).
- [ ] `StatusReader._fetch_detail_html` refuses empty-body responses
  and raises `StatusReaderError` carrying the expediente_id and
  HTTP status.

## out of scope

See D10.
