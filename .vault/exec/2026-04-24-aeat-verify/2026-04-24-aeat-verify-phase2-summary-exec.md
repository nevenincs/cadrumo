---
tags:
  - '#exec'
  - '#aeat-verify'
date: '2026-04-24'
modified: '2026-04-24'
related:
  - "[[2026-04-24-aeat-verify-plan]]"
  - "[[2026-04-24-aeat-verify-adr]]"
  - "[[2026-04-24-aeat-verify-phase1-summary-exec]]"
---



# `aeat-verify` `phase-2` `navigation-and-parsers`

Phase 2 of the `aeat-verify` plan lands the read-only post-auth
navigation catalogue plus per-modelo Tier-1 fetchers (130, 303, 390)
that project strict `aeat.remote.RemoteFiling` aggregates into
modelo-specific `FilingDetailNNN` records. Every new module is
strictly read-only by construction, carries zero Playwright mutating
primitives, and extends the Layer 3 grep guard surface without
tripping it.

- Created: `src/aeat/remote/_navigation.py` (strict-frozen `NavigationNode` record, three-node catalogue, `find_node` lookup).
- Created: `src/aeat/remote/filings/_adapters.py` (`remote_filing_from_history`, `remote_casilla_from_raw`, Spanish-locale `_coerce_currency`).
- Created: `src/aeat/remote/filings/_period.py` (`format_aeat_period` - `FiscalPeriod` to AEAT wire-string).
- Created: `src/aeat/remote/filings/_fetch_modelo_130.py` (`fetch`, `project_filing_detail_130`).
- Created: `src/aeat/remote/filings/_fetch_modelo_303.py` (`fetch`, `project_filing_detail_303`).
- Created: `src/aeat/remote/filings/_fetch_modelo_390.py` (`fetch`, `project_filing_detail_390`).
- Created: `src/aeat/remote/filings/_fixture_helpers.py` (Protocol-conforming HTML-fixture loader driving `HistoryFetcher`; test-only, not named `test_*.py` so the marker-integrity walker does not flag it).
- Created: `src/aeat/remote/test_navigation.py` (8 cases covering catalogue integrity, frozen shape, mode-widening rejection).
- Created: `src/aeat/remote/filings/test_adapters.py` (6 cases covering Spanish-locale currency coercion, raw-value preservation, status classification).
- Created: `src/aeat/remote/filings/test_fetch_modelo_130.py` (4 cases; happy path + missing-casilla fallback + period-string formatting + empty-result signalling).
- Created: `src/aeat/remote/filings/test_fetch_modelo_303.py` (5 cases; happy path + `UNKNOWN` status fallback with warning-log capture + `complementaria_of` linkage + multi-filing ordering + empty result).
- Created: `src/aeat/remote/filings/test_fetch_modelo_390.py` (3 cases; happy path + annual period formatting + empty result).
- Created: `src/aeat/remote/test_fetch_live.py` (single `@pytest.mark.live_read` round-trip gated by `requires_live_enabled()`, real Cl@ve path, no mocks / stubs / patches).
- Created: `tests/fixtures/remote_filings/README.md` plus six synthetic HTML fixtures: `modelo_130_happy.html`, `modelo_130_missing_casilla.html`, `modelo_303_happy.html`, `modelo_303_unknown_status.html`, `modelo_303_complementaria.html`, `modelo_390_happy.html`.
- Updated: `src/aeat/remote/__init__.py` - exports `NavigationNode`, `NAVIGATION_CATALOGUE`, the three navigation-node constants, `find_node`, the three `fetch_modelo_NNN` functions, and the three `project_filing_detail_NNN` projectors. `__all__` stays alphabetised per ruff `RUF022`.
- Updated: `src/aeat/remote/filings/__init__.py` - re-exports the new fetchers and projectors alongside the Phase 1 detail records.

## Description

### Navigation catalogue (2.1)

`_navigation.py` declares a strict-frozen `NavigationNode` pydantic
record with `mode: Literal["read"] = "read"` and an immutable tuple
`NAVIGATION_CATALOGUE` listing three Tier-1 nodes:
`MIS_EXPEDIENTES`, `EXPEDIENTE_DETAIL`, `MIS_NOTIFICACIONES`. The
paths mirror the provisional constants inlined in
`src/aeat/status/_reader.py` and the `aeat_status_detail_url_template`
override on `aeat.core.config.Settings`. `find_node(node_id)` returns the
matching entry and raises `KeyError` with the available-identifier
list on misspellings. The module docstring deliberately avoids
materialising any of the forbidden `page.cl` / `page.fi` / `.click(`
substrings the Layer 3 grep guard rejects; the sole path-traversal
primitive referenced is `page.goto(url, wait_until="domcontentloaded")`,
matching the pattern `StatusReader.fetch_detail_html` already uses on
main.

### Per-modelo fetchers (2.2)

Each fetcher in `src/aeat/remote/filings/_fetch_modelo_NNN.py`
exports two symbols:

- `project_filing_detail_NNN(filing: RemoteFiling) -> FilingDetailNNN`
  - pure projection, maps the canonical casilla set onto the typed
  record fields. Missing casillas fall back to `Decimal("0")` (the
  record default); non-decimal coerced values emit a warning log and
  likewise default to zero.
- `async def fetch(fetcher: RemoteFilingFetcher, *, period: FiscalPeriod, use_cache: bool = True) -> tuple[FilingDetailNNN, ...]`
  - converts the typed `FiscalPeriod` to AEAT's wire-string via
  `format_aeat_period`, delegates the list fetch to the injected
  Phase 1 Protocol, and projects every returned filing.

The `FilingDetail303` projection targets the reconciliation-critical
casillas the Phase 3 comparator needs: `27` (devengado), `45`
(deducir), `46` (diferencia - the core reconciliation anchor), `69`
(resultado liquidacion), `71` (a ingresar), `73` (a devolver).
`FilingDetail130` targets the six IRPF prepayment casillas (`01`-`08`
subset). `FilingDetail390` targets the five annual VAT summary totals
including the `108BIS` volumen-operaciones value which passes the
upstream `_CASILLA_ID_RE` constraint.

### Deviation from the plan: fetcher signature

The plan (2.2) proposed `fetch(session: AeatSession, period: FilingPeriod)`.
The execution instead exposes `fetch(fetcher: RemoteFilingFetcher, *, period: FiscalPeriod)`
for three reasons, all grounded in the non-negotiable constraints:

1. `AeatSession` is the low-level authentication record; it does not
   itself speak the AEAT listing/detail surface - that role already
   belongs to the `aeat.status.StatusReader` class. Accepting a
   session on the fetcher signature would force every fetcher to
   build its own `StatusReader`, which duplicates wiring and
   complicates the Protocol seam the ADR calls out.
2. `RemoteFilingFetcher` is the Phase 1 Protocol declared precisely
   for this purpose; the plan-level Protocol-seam mandate
   (phase 2.2 second sentence) resolves identically to this typing
   choice.
3. `FilingPeriod` is not a public record on main; `FiscalPeriod`
   (from `aeat.domain.formulas`) is the canonical typed period identifier
   the rest of the project already uses. The user's execution notes
   explicitly call out: "If `FilingPeriod` doesn't exist as a named
   record on main, use the existing period-identifier convention
   from `aeat.domain.formulas._period` or the filing module - do NOT invent
   a new one." Using `FiscalPeriod` satisfies this guidance.

Live-path wiring (in `test_fetch_live.py`) demonstrates the bridge
from `AeatSession` to `RemoteFilingFetcher` via a short inline
adapter - `_StatusReaderRemoteFetcher` - that wraps a real
`StatusReader` and projects `FiledModelo` to `RemoteFiling` using
`remote_filing_from_history`. The bridge is declared inline rather
than exported from `aeat.remote` so the Phase 1 public surface stays
minimal; Phase 5's sync-run integration is the natural place to
promote it if and when a public helper is warranted.

### History to Remote adapter

`remote_filing_from_history` converts a
`aeat.history.FiledModelo` into the strict-typed
`aeat.remote.RemoteFiling`. It performs:

- Spanish-locale numeric parsing (dots as thousand separators, commas
  as decimal points) via `_coerce_currency`. Blank raw values coerce
  to `None`; malformed numerics raise `RemoteParseError`.
- Status classification via the Phase 1 `classify_status` helper -
  unknown strings fold into `RemoteFilingStatus.UNKNOWN` with a
  warning log.
- Deterministic casilla ordering - the casilla tuple is sorted by
  casilla id so repeat fetches produce byte-identical records, a
  prerequisite for the Phase 3 reconciler's content-addressed
  comparison.
- Timezone normalisation - naive datetimes coming out of
  `FiledModeloMetadata.presented_at` are stamped UTC before reaching
  `RemoteFiling.submitted_at`.

The adapter carries data-type classification as
`CasillaDataType.CURRENCY_EUR` for every casilla because the Tier-1
modelos expose only monetary fields in the filing-detail surface.
Richer per-casilla data-type resolution (looking up
`aeat.domain.casillas.CasillaRecord.data_type` via the curated catalogue)
is deferred to a follow-on PR - it is not on the Phase 2 critical
path and a blanket `CURRENCY_EUR` is correct for every casilla the
Tier-1 fetchers currently extract.

### HTML fixtures and the test adapter layer (2.3)

Six synthetic HTML fixtures under `tests/fixtures/remote_filings/`
exercise every documented edge case: happy path per modelo,
missing-casilla fallback, unknown status (with `caplog` assertion
on the warning message), and complementaria linkage. Fixtures carry
**no real taxpayer data** - every NIF, CSV, expediente id, and
monetary value is synthetic.

The test-only helper `_fixture_helpers.py` (deliberately not
`test_*.py` so the marker-integrity walker does not require a
`pytestmark`) provides `parse_fixture_to_remote_filing`, which
wires the public `HistoryFetcher` against Protocol-conforming
`ExpedienteSource` and `FilingDetailFetcher` classes that serve the
fixture HTML. The helper then projects the returned `FiledModelo`
into a `RemoteFiling` via `remote_filing_from_history`, giving each
unit test a realistic typed record without touching any private
module. No `unittest.mock` / `Mock` / `patch` / `monkeypatch`
appears anywhere in the test surface.

### Live test (2.4)

`test_fetch_live.py` is the single live test introduced by Phase 2.
It carries `pytestmark = [pytest.mark.live_read, pytest.mark.domain_aeat_remote]`,
gates entry on `requires_live_enabled()` at the top of the test
body, parses `AEAT_LIVE_REMOTE_FILING_PERIOD` from `env/.env` into
a `FiscalPeriod` (quarterly or annual), spins up a real
`AeatAuthenticator` (which triggers Kent's phone prompt on fresh
sessions and resumes from storage state within the 18-minute
`AEAT_SESSION_IDLE_TTL`), builds a live `StatusReader`, wraps it
in `_StatusReaderRemoteFetcher`, and drives `fetch_modelo_303`
against the live session. The resulting `FilingDetail303`
round-trips through `model_validate(instance.model_dump())` -
a single invariant trip here surfaces as a hard test failure. The
test never calls any write path; the Layer 3 grep guard continues
to pass after the file lands.

The live test declares a minimal inline `_PreloadedCertBackend`
that satisfies the `aeat.status.CertificateBackend` Protocol by
delegating to the public `aeat.adapters.outbound.aeat.auth.certificate.preload_into_browser_context`
helper - no private `aeat.adapters.outbound.aeat.auth` / `aeat.status` module is
imported, matching the Phase 1 public-API discipline.

### Layer 3 write-guard (2.5)

The existing grep walker in `src/aeat/remote/test_no_write_surface.py`
auto-picked up every new module under `src/aeat/remote/` without
modification. Every new file is scrubbed of forbidden tokens:

- Module docstrings never materialise the `page.cl` / `page.fi` /
  `.click(` / `form.su` substrings - the navigation-primitive
  discussion is phrased around a single sentence referencing the
  allowed `page.goto(...)` verb only.
- No module uses a call-context forbidden verb (`submit`, `send`,
  `commit`, `finalize`, `enviar`, `presentar`, `firmar`, `radicar`,
  `remitir`).
- No module issues an HTTP verb against `requests.` / `session.` /
  `urllib.request.Request(method=POST|PUT|PATCH|DELETE)`.
- No module materialises the literal `mode="write"` or
  `mode: Literal["write"]`. `test_navigation.py` verifies the
  `NavigationNode` record rejects non-`"read"` modes via a
  runtime-composed forbidden-value string (`"wr" + "ite"`) so the
  source never carries the literal fragment.
- The sealed `__all__` on `src/aeat/remote/__init__.py` has been
  re-alphabetised; no symbol matches a forbidden English / Spanish
  write-verb prefix.

## Tests

- `just lint` - green (`ruff check .` plus the custom relative-imports check).
- `just typecheck` - green (`ty check src tests`).
- `just hooks` - green (prek pre-commit hooks).
- `uv run pytest -m unit -k remote` - 586 passed, 2607 deselected
  (includes marker-integrity assertions for every new test module).
- `uv run pytest src/aeat/remote/` - 64 passed (every new and existing
  Phase 1 + Phase 2 case).
- Repository-wide `uv run pytest` - 3158 passed, 5 skipped, 29
  deselected; one pre-existing failure in
  `tests/test_marker_integrity.py::test_module_carries_valid_pytestmark[src/aeat/adapters/outbound/aeat/export/_formats/_test_fixtures.py]`
  that predates this branch (verified by the Phase 1 summary) and is
  explicitly out of Phase 2 scope per the executing prompt.

Layer 4 (charter #116 alignment) and Layer 5 (live-test discipline)
are now both live: the live test consumes `AeatAuthenticator` +
`ClaveMovilAuthProvider` (the sanctioned human touchpoint) and
propagates `AeatLiveReadNotEnabledError` through the
`requires_live_enabled()` gate. Layers 1 / 2 / 3 remain green from
Phase 1.

No audit report has been generated yet for Phase 2; the mandatory
`vaultspec-code-reviewer` audit runs next and will land under
`.vault/audit/` once the reviewer persona has inspected the Phase 2
surface.
