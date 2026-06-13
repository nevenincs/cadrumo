---
tags:
  - "#research"
  - "#aeat-filing-detail-fetch"
date: 2026-04-18
modified: '2026-04-18'
title: Research — StatusReader.fetch_filing_detail (#227)
issue: wgergely/aeat#227
epic: wgergely/aeat#70
related:
  - "[[2026-04-12-status-reader-adr]]"
  - "[[2026-04-16-aeat-history-fetch-adr]]"
---

# research — StatusReader.fetch_filing_detail (#227)

## problem

Kent cannot amend a previously filed return without first re-reading
its *casilla-level* values from AEAT. The Kent-revise audit explicitly
names this gap as **wall 23**:

> Even when live AEAT reads work, there is no surface that fetches
> previously-filed casilla values. For amendments to be usable at
> scale, the tool must be able to read what it is amending. This is a
> missing `StatusReader.fetch_filing_detail(modelo, period)` (or
> equivalent portal scrape) — the entire amendment flow is load-bearing
> on it. — `.vault/audit/2026-04-17-kent-revise-review-audit.md:50`

Issue #227 ("P1-Blk: Implement
`StatusReader.fetch_filing_detail(modelo, period)`") is the surface
that closes wall 23. It also unblocks wall 11 (live filing-history
retrieval) and walls 21–22 (amendment import / PDF casilla fallback)
as a composable read-only entrypoint.

## existing surfaces

The read side of the AEAT loop already has the ingredients:

- `aeat.status.StatusReader` (merged via #43)
  - Drives a Playwright `BrowserContext` with a preloaded certificate.
  - `fetch_expedientes(*, since=None, use_cache=True) ->
    tuple[Expediente, ...]` lists the user's filing headers.
  - Every other `fetch_*` method is a "not yet implemented"
    placeholder.
- `aeat.history.HistoryFetcher` (merged via #168/#195)
  - Composes two injected Protocol collaborators:
    - `ExpedienteSource.list_expedientes(*, modelo, period) ->
      tuple[Expediente, ...]`
    - `FilingDetailFetcher.fetch_detail_html(expediente) ->
      (html, url)`
  - Routes each detail HTML through the per-modelo parser registry
    (`parse_filing_detail`, `PARSER_REGISTRY`) and persists to
    `AEAT_FILING_HISTORY_DIR/history.json`.
- `aeat.history._parsers` (pure functions)
  - `parse_modelo_130_detail`, `parse_modelo_303_detail`,
    `parse_modelo_390_detail` — all delegate to
    `build_filed_modelo()` in `_common.py`.
  - The casillas table + headline totals extraction is already
    battle-tested against `tests/fixtures/aeat-pages/filing-history/`.
- `aeat.history._models` boundary types
  - `FiledModelo` (metadata + `RawCalculationPayload` + warnings).
  - `FiledModeloMetadata` includes `complementaria_of` so amendment
    lineage round-trips cleanly.
  - `RawCalculationPayload.casillas: dict[str, str]` (raw strings,
    typed downstream by the verification engine).

The missing piece is the **live driver** that:

1. Lists expedientes for `(modelo, period)` against the authenticated
   portal (this is a thin wrapper over `fetch_expedientes`).
2. Navigates to the detail page for each expediente and returns the
   raw HTML + resolved URL.
3. Exposes a single ergonomic entrypoint on `StatusReader` that
   composes both into `tuple[FiledModelo, ...]`.

## constraints (binding)

- **Read-only (non-negotiable).** The live-AEAT-write safety charter
  (#116) and history-fetch ADR D1 both forbid navigation to write
  surfaces. Every interaction must be `page.goto(url,
  wait_until="domcontentloaded")` + `page.content()`. No form fills,
  no clicks beyond link-following navigation that the HTTP verb
  guarantees is GET.
- **Strict pydantic v2 at boundaries.** `FiledModelo` is already
  strict+frozen; we reuse it. No new boundary types unless strictly
  required.
- **No mocks / fakes / patches.** Unit tests must use real
  Protocol-conforming classes (the testing charter mirrors
  `aeat.history.test_fetcher` patterns).
- **`src/aeat/` relative imports.** Within the subpackage, use
  `.module` / `..sibling`. Never `aeat.*` absolute.
- **No circular imports.** `aeat.history` already imports
  `Expediente` from `aeat.status`. Any reverse dependency
  (`aeat.status` → `aeat.history`) must be deferred / function-scoped
  to keep module import order safe.
- **Preserve the #43 Protocol stubs.** The status reader's
  `_protocols.py` (`BrowserSessionLike`, `CertificateBackend`) is the
  contract boundary; do not add hard imports to `aeat.adapters.outbound.aeat.auth` /
  `aeat.adapters.outbound.aeat.browser`.

## portal surface — what we know

### "Mis expedientes" listing

- Endpoint: `/wlpl/TC-UTIL/Expediente?COPT=Y` (in
  `_reader._EXPEDIENTES_PATH`).
- Columns captured by `parse_expedientes`:
  `Expediente | Modelo | Periodo | Estado | Fecha presentacion | CSV
  | Justificante`.
- Each row currently yields `Expediente.justificante_url` when a
  `<a href>` is present under the `Justificante` column. Live AEAT
  expedientes typically expose the PDF justificante *and* a separate
  HTML "Detalle" link; v1 of the parser only harvested the PDF
  anchor. This is load-bearing because the PDF is not the casilla
  surface the history parsers consume — we need the rendered HTML
  detail page.

### "Detalle" page (HTML)

- We do not yet have a captured live URL pattern — this work is done
  offline pending the #8/#43 live bring-up. From AEAT's public
  documentation (`https://sede.agenciatributaria.gob.es/Sede/`) the
  detail page URL shape observed in the wild is typically one of:
  - `/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}`
  - `/wlpl/TC-UTIL/Expediente/ConsultaPresentaciones?...`
- The history parsers (`_common.find_casillas_table`) key on either
  `class="casillas"` or a `<th>Casilla</th>` + `<th>Valor</th>`
  header, which matches AEAT's rendered HTML across all three
  modelos (130 / 303 / 390) observed in fixtures.
- The HTML detail page is a stable surface — AEAT does not paginate
  filing details and does not fetch additional content over XHR for
  the casilla table. A single `page.goto(...)` + `page.content()`
  suffices.

### detail-URL discovery path

The v1 implementation must not block on perfect URL templating:

1. **Primary source — parser enhancement.** When AEAT renders a
   dedicated HTML-detail anchor in the expediente row (commonly under
   an `Acciones` / `Detalle` column), we can extend
   `parse_expedientes` to capture it into a new
   `Expediente.detail_url: AnyHttpUrl | None` field. This is
   backwards-compatible (default `None`) and preferred because the
   portal is the authoritative source for the URL shape.
2. **Fallback — templated construction.** When `detail_url` is
   unavailable (older fixtures, certain campaign years), construct
   the URL from a module-level template:
   `urljoin(aeat_base_url, _EXPEDIENTE_DETAIL_PATH_TEMPLATE.format(expediente_id=...))`
   with `_EXPEDIENTE_DETAIL_PATH_TEMPLATE` declared as a module
   constant (default
   `"/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}"`).
   Operators who run against a different campaign URL can override
   via an env-var-driven Settings field (`AEAT_STATUS_DETAIL_URL_TEMPLATE`).
3. **justificante_url is not a substitute.** The justificante PDF
   has no casilla table. The ADR must explicitly forbid falling back
   to `justificante_url` for the HTML detail fetch.

## architectural options

### option A — StatusReader as composite implementer (recommended)

`StatusReader` structurally implements **both** `ExpedienteSource`
and `FilingDetailFetcher` (no subclassing — the Protocols are
structural via `@runtime_checkable`). A new public method
`fetch_filing_detail(modelo, period, *, use_cache=True)` composes
them via a function-scoped `HistoryFetcher`.

```
StatusReader
  ├── fetch_expedientes(*, since, use_cache)        # existing (#43)
  ├── list_expedientes(*, modelo, period)           # new, thin wrap
  ├── _fetch_detail_html(expediente) -> (html, url) # new, navigates
  └── fetch_filing_detail(modelo, period, *, use_cache)
        → tuple[FiledModelo, ...]
         (internally: HistoryFetcher(expediente_source=self,
                                     detail_fetcher=self,
                                     settings=self._settings)
            .fetch_for_modelo(modelo, period))
```

- **Pros:** single public entrypoint exactly matching the #227 issue
  title. Zero new top-level modules. Reuses the full `HistoryFetcher`
  cache, persistence, and parser-registry machinery unchanged.
- **Cons:** introduces a cross-subpackage import (`aeat.status` →
  `aeat.history`). Mitigated by function-scoped (deferred) import
  inside `fetch_filing_detail` — `aeat.history` already imports
  `Expediente` from `aeat.status`, but the reverse direction only
  executes when the composite method is called, so the module-load
  DAG stays acyclic.
- **Cons:** couples StatusReader v2 scope to modelos supported by
  `aeat.history` (130 / 303 / 390 today). Acceptable — unsupported
  modelos already raise `HistoryUnsupportedModeloError` with a clear
  message.

### option B — dedicated facade module

Create `aeat.status._filing_detail` that wraps `StatusReader` and
constructs the `HistoryFetcher`, exposing `fetch_filing_detail` as a
top-level function.

- **Pros:** zero reverse-direction import inside `StatusReader`.
- **Cons:** violates #227 which literally specifies
  `StatusReader.fetch_filing_detail(modelo, period)`. Splits a
  related feature across two call sites. Rejected.

### option C — move parsers into `aeat.status`

Move `aeat.history._parsers` under `aeat.status._parsers` and drop
the reverse import entirely.

- **Pros:** cleanest import DAG.
- **Cons:** massive, out-of-scope refactor. `HistoryFetcher`,
  persistence, CLI wiring, tests, fixtures, and the #168 ADR all
  move. Rejected as scope creep.

### verdict

**Option A**. Minimal surface addition, exact match to #227 title,
reuses all existing infrastructure, circular-import avoided by
function-scoped import.

## signature — shape of the new public method

```python
class StatusReader:
    async def list_expedientes(
        self,
        *,
        modelo: str | None = None,
        period: str | None = None,
        use_cache: bool = True,
    ) -> tuple[Expediente, ...]:
        """Filter-aware listing (implements ExpedienteSource Protocol)."""

    async def fetch_filing_detail(
        self,
        modelo: str,
        period: str,
        *,
        use_cache: bool = True,
    ) -> tuple[FiledModelo, ...]:
        """Fetch every filed modelo matching (modelo, period).

        Lists expedientes filtered by (modelo, period), navigates to
        each expediente's detail page, parses the casilla→value
        mapping, and returns strict pydantic records.

        Raises:
            HistoryUnsupportedModeloError: if the modelo has no parser.
            StatusParseError / HistoryParseError: on malformed HTML.
            StatusAuthError: on navigation failure.
        """
```

Key points:

- Both `modelo` and `period` are **required** on
  `fetch_filing_detail` (unlike `list_expedientes`). This matches the
  #227 title and forces callers to scope the fetch — a naked
  `fetch_filing_detail()` would be an unbounded operation.
- Return type is `tuple[FiledModelo, ...]` (existing type in
  `aeat.history`). The local-state domain that downstream consumes
  this already has `FiledModelo` affordances via `aeat.history`.
- `use_cache` defaults to True, matching the project convention
  (#43 D8, #168 D8).
- Errors are reused. No new error class needed — this is a
  composition layer.

## testing strategy

Following the #43 and #168 patterns:

- **Unit (`pytest.mark.unit`, `domain_aeat_remote`).**
  - Real Protocol-conforming `BrowserSessionLike` and
    `CertificateBackend` test doubles — no mocks.
  - Fixture-based HTML for both the expediente listing and the
    detail pages.
  - Cover:
    - `list_expedientes(modelo=..., period=...)` filter semantics.
    - `_fetch_detail_html` URL construction (primary +
      `detail_url`-in-expediente + templated fallback).
    - `fetch_filing_detail(modelo, period)` end-to-end composition:
      list → detail HTML → parse → FiledModelo.
    - Empty result when no expediente matches.
    - Empty-casilla filings surfaced via `parse_warnings`, not
      raised.
    - Unsupported modelo raises `HistoryUnsupportedModeloError`.
    - Cache hit path does not re-navigate.
- **Live (`pytest.mark.live_read`, `domain_aeat_remote`).**
  - Skipped by default. When `AEAT_LIVE_TESTS_ENABLED=1` is set
    and cert backend is available, exercise against a real AEAT
    session.
  - Deferred while #8/#41 live bring-up is still under stabilisation
    (see `src/aeat/status/test_live.py`); the placeholder test
    should add a parallel skip for `fetch_filing_detail` with the
    same rationale.

## risks and mitigations

| risk | severity | mitigation |
|---|---|---|
| Detail URL template drifts per campaign | medium | Make template overrideable via Settings; prefer parser-captured `detail_url` when present |
| Circular import between status and history | low | Function-scoped import; module-load DAG stays acyclic |
| Unsupported modelos raise an opaque error | low | Re-raise `HistoryUnsupportedModeloError` with the full list of supported modelos |
| Test-double drift — double doesn't match Playwright `page.goto` semantics | low | Use real Protocol-conforming classes (not mocks); follow the #168 test pattern |
| Someone wires this into a write path | CRITICAL | Code review checklist: rg for POST/form.submit/page.fill inside status; ADR D1 mirror; no write-intent verbs in public surface |

## prior art references

- `src/aeat/status/_reader.py:224` — `fetch_expedientes` pattern.
- `src/aeat/history/_fetcher.py:214` — `fetch_for_modelo` pattern to
  emulate.
- `src/aeat/history/_fetcher.py:170` — `_resolve_expediente` cache
  logic to reuse unchanged.
- `src/aeat/history/_parsers/_common.py:225` — `build_filed_modelo`
  is already the reusable parser backbone.
- `src/aeat/history/test_fetcher.py` — `_FakeExpedienteSource` +
  `_FakeDetailFetcher` are the canonical real-class test double
  patterns.

## conclusion

Implement #227 as **Option A**: `StatusReader` structurally
implements both `ExpedienteSource` and `FilingDetailFetcher`,
exposing `fetch_filing_detail(modelo, period)` as the single public
composite entrypoint. Reuse `HistoryFetcher` for orchestration and
`aeat.history._parsers` for parsing. Circular import avoided by
function-scoped import inside `fetch_filing_detail`. No new boundary
types; `FiledModelo` remains authoritative. Tests follow the #168
real-Protocol-class doubles pattern.

The ADR that follows this research pins these decisions and their
enforcement surface.
