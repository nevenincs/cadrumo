---
tags:
  - "#adr"
  - "#aeat-history-fetch"
date: 2026-04-16
modified: '2026-04-16'
title: AEAT filing-history read surface — ADR
related:
  - "[[2026-04-16-aeat-history-fetch-research]]"
  - "[[2026-04-12-status-reader-adr]]"
  - "[[2026-04-12-notifications-inbox-adr]]"
issue: wgergely/aeat#168
epic: wgergely/aeat#166
status: accepted
---

# adr: aeat filing-history read surface

## context

The double-entry verification engine (a downstream deliverable of
EPIC #166) needs to compare locally computed filing drafts against
the casilla-level data AEAT actually received. Neither the #43 status
reader (returns `Expediente` headers only) nor the #44 justificante
parser (returns headline totals only) exposes this payload.

Issue #168 builds the missing read surface: a
`src/aeat/history/` subpackage that, given the list of `Expediente`
headers, fetches the per-filing detail page, parses the casilla→value
mapping, and persists the result as strict pydantic v2 records.
See `[[2026-04-16-aeat-history-fetch-research]]` for the portal
surfaces, parser choice, and wire-schema background.

## decisions

### D1: the fetcher is read-only against AEAT

`HistoryFetcher` never POSTs, never submits a form, and never
navigates to a surface that mutates AEAT state. The public API
contains zero write-intent verbs (no `submit`, `send`, `ack`,
`acknowledge_remote`, `mark_*`). Every browser interaction is a
`page.goto(url, wait_until="domcontentloaded")` followed by
`page.content()`.

**Rationale:** the live-AEAT-write safety charter (#116) is
non-negotiable. AEAT has no sandbox and every write is legally
binding. This issue sits on the read axis of EPIC #166; write surfaces
are a separate-issue-separate-safety-review discipline.

Enforcement (mechanical, asserted in the code-review step):

1. `rg -n 'page\.(fill|click|type|select_option|check|press|set_input_files)|form\.submit|\.click\(\)' src/aeat/history/`
   returns **zero** matches.
2. No public method name on any exported class or module matches
   the regex `/(submit|send|ack|acknowledge|mark_|confirm|file_|post_)/i`.
3. Every `page.goto(...)` call is documented in the code-review
   checklist with the target URL and a justification line.

### D2: two-step composition via Protocol stubs

`HistoryFetcher` composes two injected collaborators:

```python
@runtime_checkable
class ExpedienteSource(Protocol):
    async def list_expedientes(
        self,
        *,
        modelo: str | None = None,
        period: str | None = None,
    ) -> tuple[Expediente, ...]: ...

@runtime_checkable
class FilingDetailFetcher(Protocol):
    async def fetch_detail_html(
        self,
        expediente: Expediente,
    ) -> tuple[str, AnyHttpUrl]: ...
```

The real `ExpedienteSource` wraps `aeat.status.StatusReader`; the real
`FilingDetailFetcher` wraps the same `BrowserSession`. Tests supply
real Protocol-conforming classes returning fixture tuples and fixture
HTML strings respectively — **no** `unittest.mock`, **no** patches,
**no** fakes, per the project testing charter.

**Rationale:** mirrors the proven #43 + #46 pattern. Decouples the
fetcher from the in-flight #167 cert-auth work, which we compose via
the browser session Protocol rather than import directly. Rebase on
merge is a one-file Protocol-removal diff.

### D3: casilla values are carried as strings, not typed

`RawCalculationPayload.casillas` is `dict[str, str]` keyed by
`casilla_id`. Values are the raw portal-rendered strings
(`"1.234,56"`, `"0,00"`, `"31/12/2025"`).

**Rationale:** AEAT's wire format mixes Spanish-locale decimals,
dates, and booleans freely, and the typed shape lives in
`aeat.domain.casillas.CasillaRecord.data_type`. Typing at this boundary
would force the fetcher to embed a copy of the casilla catalogue,
duplicating #6 and creating two sources of truth. The verification
engine (downstream) is the correct place to coerce via
`CasillaRecord.data_type` — it is the only consumer that owns the
catalogue join. Headline totals (`total_a_ingresar`, etc.) are an
exception: they are extracted as `Decimal` because they are labelled
verbatim on every fixture and because downstream reconciliation wants
a comparable numeric.

### D4: every boundary type is strict + frozen pydantic v2

`FiledModeloMetadata`, `RawCalculationPayload`, `FiledModelo`, and
`FilingHistory` all use
`ConfigDict(strict=True, frozen=True, extra="forbid")`. Closed
enumerations are `enum.StrEnum`. No dataclasses and no bare
`dict[str, Any]` on public surfaces, **except** the
`RawCalculationPayload.casillas: dict[str, str]` which is strict (str
keys, str values, validated on ingestion). Persisted history file is
`FilingHistory.model_dump_json()` and loaded via
`FilingHistory.model_validate_json()`.

**Rationale:** project-wide pydantic v2 mandate (memory: pydantic
mandate). The history layer crosses three boundaries — wire (HTML
parse), disk (JSON file), and CLI (query/list) — so the model is the
validation gate for all three.

### D5: per-modelo parsers, deterministic and pure

Each supported modelo owns a parser module under
`src/aeat/history/_parsers/` with a pure function signature:

```python
def parse_<modelo>_detail(
    raw_html: str,
    *,
    expediente: Expediente,
    source_url: AnyHttpUrl,
    fetched_at: datetime,
) -> FiledModelo: ...
```

Parsers never perform I/O, never touch the browser, and never reach
out to network. They are exercised entirely against fixture HTML
under `tests/fixtures/aeat-pages/filing-history/<modelo>_<variant>.html`.

**Rationale:** mirrors the #43 parsers-are-pure decision (D8 in the
status reader ADR). Makes the unit test suite fully offline and
deterministic.

### D6: v1 covers modelo 130, 303, 390; others raise

`HistoryFetcher.fetch_filed_modelo(expediente)` routes to the right
parser via a `dict[str, Callable]` registry. Unknown modelos raise
`HistoryUnsupportedModeloError` with a clear "not yet supported
(#168 follow-up)" message listing the supported set.

**Rationale:** matches the #43 v1 scoping (one surface wired,
others stub). The three modelos listed are the exact set covered by
the existing casilla catalogue (`ModeloCode` enum), so we ship
complete coverage for every modelo the project already supports.

### D7: persistence is a single JSON file under a dedicated dir

`FilingHistory` persists to
`AEAT_FILING_HISTORY_DIR/history.json`. No sqlite, no storage-layer
wiring, no per-modelo sharding. Raw HTML snapshots (opt-in,
controlled by `AEAT_FILING_HISTORY_ARCHIVE_HTML=1`) go under a
sibling `pages/` subdirectory, keyed by
`<expediente_id>.html`.

**Rationale:** matches the #46 inbox cadence exactly. The #10
storage layer is not yet on main; #168 should not block on it. The
v1 file shape is trivially migratable to the storage layer in a
follow-up.

### D8: cache is advisory; every consumer can bypass

The fetcher supports `use_cache: bool = True` on every public fetch
method. When True (default), a cached `FiledModelo` is returned if
`now - fetched_at < aeat_filing_history_cache_ttl_s`. When False,
the detail page is re-fetched.

**Rationale:** mirrors the #43 cache policy (D5 there). Consumers
that want freshness can have it without running the collector
cold-start. Cache is revalidated through the pydantic model on read,
so stale payloads cannot leak stale shapes.

### D9: status-reader, auth, and browser-session are all Protocol stubs

Inside `src/aeat/history/_protocols.py` we declare:

- `ExpedienteSource` — as above; swapped out on merge for the real
  `aeat.status.StatusReader` facade.
- `FilingDetailFetcher` — as above; swapped out on merge for a
  real facade wrapping `aeat.adapters.outbound.aeat.browser.BrowserSession`.
- `CertificateBackend` — a structural mirror of the one in
  `aeat.status._protocols`. We do **not** cross-import from
  `aeat.status._protocols` (it is a private module per #43's
  underscore convention); we declare the identical minimal surface
  locally. The public `aeat.adapters.outbound.aeat.auth.certificate` module already ships a
  real `CertificateService` on main, but the local Protocol stub
  exists so unit tests can construct a `HistoryFetcher` without
  spinning up a real browser session or certificate backend — the
  test double conforms structurally without importing the real
  backend at all. #167 does not block this ADR.

**Rationale:** zero hard-imports from sibling subpackages' private
modules. Matches the #43 pattern. Unit tests stay 100 % offline
because the Protocol surface is the contract, not the implementation.

### D10: non-goals are explicit

The fetcher does **not**:

- Submit anything to AEAT — see D1.
- Draft, rectify, or file complementarias.
- Type casilla values (see D3).
- Parse PDF duplicates — HTML detail only in v1; PDF is a follow-up.
- Persist to the storage layer (#10).
- Integrate with the verification engine — it *produces* the input
  that engine consumes.

These are documented in the package docstring.

### D11: parse warnings are surfaced, not raised

Partial / rejected filings (`status == "Rechazada"`, `"En
tramitación"`) may yield an empty `casillas` dict. The parser
collects a tuple of short human-readable warnings on
`FiledModelo.parse_warnings` rather than raising. A fully-empty
payload is still a valid `FiledModelo` with `parse_warnings=(…,)`
describing what was missing.

**Rationale:** rejecting empty payloads would require the caller to
special-case rejected filings, which is a footgun. Downstream
consumers (verification) can filter by `parse_warnings` or
`metadata.status`.

### D12: decimal parsing reuses #44's extractor

`_parse_decimal` in the new `aeat.history._decimal` module is
copy-and-documented from
`aeat.domain.justificante._extract._parse_decimal`. We do **not** cross-
import from `_extract` (it is private to the justificante
subpackage). Duplication is preferred to coupling because the
Spanish-locale parser is a 15-line pure function and both packages
need it, but neither owns the other. If we grow a third consumer,
promote to `aeat._decimal`.

**Rationale:** respects the #162 subpackage-boundary rule. A 15-line
duplication is a lower cost than an underscored cross-import.

## consequences

- The filing-history read surface becomes available on main without
  hard-imports from #167 (cert auth) or post-#43 work on the
  `StatusReader` facade.
- Rebase onto #167 and the fuller `StatusReader` is a `_protocols.py`
  one-file diff.
- The verification engine (future issue) consumes
  `FiledModelo.metadata` + `FiledModelo.calculations` directly.
- Per-modelo parser expansion beyond 130/303/390 is a one-module
  addition plus one fixture.
- Live testing requires `AEAT_LIVE_TESTS_ENABLED=1` plus a working
  certificate backend; the #116 live-write safety charter does
  **not** apply because the fetcher is read-only — live-read tests
  are permitted.

## out of scope

See D10.
