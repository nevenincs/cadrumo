---
tags:
  - "#plan"
  - "#status-reader"
id: 2026-04-12-status-reader-plan
title: Plan — AEAT status reader (#43)
date: 2026-04-12
modified: '2026-04-12'
status: approved
type: plan
related:
  - "[[2026-04-12-status-reader-adr]]"
  - "[[2026-04-12-status-reader-research]]"
---

# Plan — AEAT status reader (#43)

## Goal

Ship the read-only AEAT status reader as `aeat.status`, with strict
pydantic v2 wire schemas for every surface, a fully-wired
**expedientes** parser, private parser stubs for the remaining five
surfaces, a cache, a `StatusReader` driver, CLI subcommands, and
unit tests.

## Pre-conditions

- `uv sync` green.
- `uv run vaultspec-core install` already completed for this
  worktree (it is).
- Sibling branches' territory respected (no touching
  `[tool.pytest]`, `conftest.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate`, or
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/`).

## Workstreams

### W1 — Dependencies and config

1. Add `beautifulsoup4>=4.12` to `[project] dependencies` in
   `pyproject.toml`.
2. Add `AEAT_STATUS_CACHE_DIR`, `AEAT_STATUS_CACHE_TTL_S`,
   `AEAT_STATUS_BROWSER_TRACE_DIR` fields to
   `src/aeat/config.py`, grouped in a new `Status reader (#43)`
   block.
3. Mirror the three variables in `env/.env.example`.
4. `tests/test_config.py` alignment check passes.

### W2 — Core models and errors

Files under `src/aeat/status/`:

- `_errors.py` — `StatusReaderError`, `StatusAuthError`,
  `StatusParseError`, `StatusNotFoundError`, all inheriting from
  `aeat.core.errors.AeatError`.
- `_models.py` — `AeatStatusKind`, `PayorKind`, `Expediente`,
  `Notificacion`, `Devolucion`, `BorradorIrpf`, `Payor`,
  `DatosFiscales`, `CalendarioEntry`. All strict + frozen +
  `extra="forbid"`.
- `_protocols.py` — `CertificateBackend` Protocol (matching
  planned #8 surface).

### W3 — Cache

- `_cache.py`: `StatusCache` dataclass-free class that takes a
  `Path` and a `ttl_s: int`. Methods `get(key: str, model: type[T])
  -> T | None` and `put(key: str, record: T) -> None`, where `T:
  BaseModel`. Hit/miss telemetry via `get_logger(__name__)`.
- `_cache_key.py` — pure function turning
  `(tax_id, surface, params)` into a stable sha256 hex key.

### W4 — Parsers

- `_parsers/__init__.py` — re-exports.
- `_parsers/expedientes.py` — FULL implementation. Uses
  BeautifulSoup4, selects the canonical `<table>`, resolves each
  row into an `Expediente`.
- `_parsers/notificaciones.py`, `devoluciones.py`, `borrador.py`,
  `datos_fiscales.py`, `calendario.py` — stub modules. Each
  exposes a `parse_*` function raising `NotImplementedError` with a
  pointer to the follow-up issue, plus a fixture-loading test.

### W5 — Reader

- `_reader.py` — `StatusReader`:
  - `__init__(browser_session, cert_backend, cache, settings,
    tax_id)`.
  - Lazy auth: `_ensure_ready()` preloads the cert, creates the
    context, and stores a single `Page`.
  - `async fetch_expedientes(*, since=None, use_cache=True)` →
    `tuple[Expediente, ...]`.
  - Stub `fetch_*` methods for the other five surfaces raising
    `StatusReaderError("surface not yet implemented (#43 follow-up)")`.
  - All public methods async; Google-style docstrings; logging via
    `aeat.core.logging.get_logger(__name__)`.

### W6 — Public API

- `src/aeat/status/__init__.py` re-exports: models, enums,
  errors, `StatusReader`, `CertificateBackend`. Public API
  discipline: callers import from `aeat.status` only.

### W7 — CLI

- `src/aeat/entrypoints/cli/status/__init__.py` — typer sub-app `app` with one
  command per surface. Default pretty-table output, `--json`
  opt-in. The commands construct a `StatusReader` via
  `_build_reader()` which calls `aeat.adapters.outbound.aeat.browser.BrowserSession`.
  Stub surfaces emit `typer.Exit(1)` with a clear message until
  their parsers land.
- Register the sub-app in `src/aeat/entrypoints/cli/__init__.py` as
  `app.add_typer(status_module.app, name="status", …)`.

### W8 — Tests

All unit tests live inside `src/aeat/status/` (Rust-style
colocated) and carry `@pytest.mark.unit`:

- `test_models.py` — every schema accepts a canonical payload and
  rejects a malformed one (type-mismatch, missing required field,
  extra field).
- `test_errors.py` — every error subclasses `AeatError`.
- `test_cache.py` — hit / miss / TTL-expiry / schema-mismatch
  invalidation.
- `test_cache_key.py` — stable keys, param-order-insensitive.
- `_parsers/test_expedientes.py` — parses the real fixture under
  `tests/fixtures/aeat-pages/expedientes/sample.html`.
- `_parsers/test_stubs.py` — each stub parser raises
  `NotImplementedError`.
- `test_reader.py` — `StatusReader` composes correctly against a
  real Protocol-conforming test double (not a mock). Stub
  surfaces raise `StatusReaderError`.
- `test_live.py` — `@pytest.mark.live`, skipped unless
  `AEAT_LIVE_TESTS=1`, one fetch per surface. Documented as
  potentially affected by the #41 `playwright_stealth` bug.

### W9 — Fixtures

- Create `tests/fixtures/aeat-pages/expedientes/sample.html`
  (trimmed, PII-scrubbed).
- `tests/fixtures/aeat-pages/README.md` documents the trimming
  procedure (also captured in the ADR).

### W10 — Vaultspec artefacts

- Research, ADR, plan, exec records under `.vault/`.

## Plan review

**Reviewer:** executing team (self-review, per vaultspec
end-to-end pipeline, no human-in-the-loop).

**Outcome:** APPROVED.

Notes from the review pass:

- Scope matches issue #43 acceptance criteria.
- Protocol stub for #8 prevents collision with the in-flight
  cert-auth branch.
- No territory collision with #15 (`[tool.pytest]`, `conftest.py`),
  #14, #42 (only compose BrowserSession, no other overlap), #16
  (browser on main), #20 (i18n on main), #11 (sync on main).
- BeautifulSoup4 is a new runtime dep; justified in the ADR.
- Live test is explicitly opt-in and documented as possibly
  failing due to the unresolved #41 stealth bug — not a blocker.
- Public API discipline respected: callers import from
  `aeat.status` only.

## Execution order

1. Pyproject dep add + uv sync.
2. Config + env additions + `tests/test_config.py` green.
3. Errors + models + protocols.
4. Cache + cache key.
5. Parsers (expedientes full, others stubbed).
6. StatusReader.
7. Public `__init__`.
8. CLI status sub-app + registration.
9. Fixtures + unit tests.
10. `just lint && just typecheck && just test && just hooks`.
11. Exec record + code review note.
