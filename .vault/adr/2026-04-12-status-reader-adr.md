---
tags:
  - "#adr"
  - "#status-reader"
id: 2026-04-12-status-reader-adr
title: ADR — AEAT status reader (#43)
date: 2026-04-12
modified: '2026-04-12'
status: accepted
type: adr
related:
  - "[[2026-04-12-status-reader-research]]"
---

# ADR: AEAT status reader (#43)

## Context

Issue #43 delivers the read-only half of the tax loop: fetch the
user's AEAT status pages, parse them into strict typed records, and
hand them back to the rest of the project. This ADR pins the
architectural decisions that govern the work.

## Decisions

### D1 — All fetches go through `aeat.adapters.outbound.aeat.browser.BrowserSession`

No raw `httpx`. The browser session already handles proxy, evasion,
profile, and (via #8) certificate preload. The status reader
composes a single `BrowserSession` instance and drives navigation
via `page.goto(...)`; raw HTML is captured from `page.content()`.

### D2 — Reader is READ-ONLY

No POST, no form submission, no cookie mutation beyond what a plain
navigation performs. The reader has no write surface in its public
API. This is enforced by the module contract and the code-review
checklist.

### D3 — HTML parser: BeautifulSoup4

BeautifulSoup4 is added as a runtime dependency. Justification:

- Pure-Python, no C build chain on Windows.
- Lenient parsing tolerates AEAT's idiosyncratic markup across
  campaigns.
- Supports "select by header text" idioms trivially.
- The reader caches raw HTML and parses it offline, so the perf
  advantage of lxml / selectolax is immaterial.

Rejected: `lxml` (C build, strictness fights AEAT markup),
`selectolax` (C build, narrower API), `html.parser` stdlib (verbose
selection model), Playwright DOM extraction (ties parsing to a live
browser and breaks fixture-based tests).

### D4 — Strict pydantic v2 everywhere

Every record crossing the module boundary is a strict, frozen
pydantic v2 `BaseModel`:

```python
model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
```

Closed enumerations are `enum.StrEnum`. No dataclasses for
boundary-crossing types. No bare `dict[str, Any]` on public
signatures or persisted files. Records revalidate on cache load so
stale payloads cannot leak stale shapes.

### D5 — Cache policy

- File-based, under `AEAT_STATUS_CACHE_DIR` (default
  `<repo>/var/status-cache`).
- Key = `sha256(tax_id || surface || query_params_json)` truncated
  to 16 hex chars, sharded by surface into subdirectories.
- Payload = pydantic-serialised JSON of the record(s), plus a
  sidecar `.meta.json` with `{cached_at, ttl_s}`.
- TTL default 900 s, configurable via `AEAT_STATUS_CACHE_TTL_S`.
- On read: if `now - cached_at > ttl_s`, miss; otherwise revalidate
  the payload through the record schema and return. Schema-mismatch
  is treated as a miss (the cache is advisory).
- Cache is advisory: every consumer can call with a `use_cache=False`
  override; callers that want freshness get it.

### D6 — Lazy authentication

`StatusReader` does not preload the certificate or navigate at
construction time. The first `fetch_*` call triggers the certificate
preload (via the Protocol-typed cert backend) and the initial login
navigation. Subsequent calls reuse the same `BrowserContext`.

### D7 — Cert backend via Protocol stub

We do not import from `aeat.adapters.outbound.aeat.auth.certificate`. Instead we declare a
`CertificateBackend` `Protocol` in `src/aeat/status/_protocols.py`
with the minimal surface we need:

```python
class CertificateBackend(Protocol):
    async def preload_into_browser_context(
        self, context: BrowserContext
    ) -> None: ...
```

A real implementation can be injected at construction time; tests
supply a real Protocol-conforming class (never a mock).

### D8 — Parsers are private, pure, deterministic

Every parser lives under `src/aeat/status/_parsers/` as a private
module. Signature: `(raw_html: str, *, source_url: AnyHttpUrl,
fetched_at: datetime, …) -> TypedRecord`. Parsers never perform
I/O and never reach out to the browser; they are exercised in tests
against fixture HTML.

### D9 — Fixture curation

Fixtures under `tests/fixtures/aeat-pages/<surface>/` are
hand-trimmed. The trimming procedure (documented so contributors
can refresh them):

1. Save the full `page.content()` from a live authenticated
   session (or the AEAT anónimo demo page if available).
2. Strip all `<script>`, `<style>`, `<link>`, `<meta>` and every
   `<div>` not ancestor to the target `<table>`.
3. Scrub PII: replace the tax id with `X1234567L`, employer tax ids
   with `A12345678`, amounts with round numbers, and any URL query
   tokens with stable placeholders.
4. Save under `tests/fixtures/aeat-pages/<surface>/<name>.html`.
5. Assert in the parser unit test that the fixture round-trips
   through the parser and through the pydantic model.

### D10 — v1 coverage

The v1 deliverable ships:

- A fully-wired **expedientes** parser exercised against a real
  fixture, end-to-end through the `StatusReader`.
- **Wire schema + parser stub (raising `NotImplementedError`) for
  every other surface**, with wire-schema unit tests covering both
  accept-cases and malformed-payload rejects.
- A live opt-in test harness that runs when `AEAT_LIVE_TESTS=1`,
  skipped by default. Known to potentially hit the #41
  `playwright_stealth` bug; the unit tests are the proof of
  correctness.

## Consequences

- Users get a typed, read-only view of their AEAT state today, with
  one surface fully wired and the rest schema-ready.
- The sync runner (#11) will replace its `WireFilingEntry` etc.
  stubs with these records in a follow-up PR.
- The storage layer (#10) can persist these records without further
  schema work — they are already pydantic v2.
- Adding a runtime dep (`beautifulsoup4`) is a one-time cost,
  isolated to the status reader's parsers.
