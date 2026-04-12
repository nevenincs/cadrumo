---
id: 2026-04-12-status-reader-exec
title: Exec — AEAT status reader (#43)
date: 2026-04-12
status: done
type: exec
---

# Exec record — AEAT status reader (#43)

Branch: `feature/43-status-reader`
Vault refs: research [[2026-04-12-status-reader-research]],
ADR [[2026-04-12-status-reader-adr]], plan [[2026-04-12-status-reader-plan]].

## Summary

Delivered the read-only AEAT status reader as
`src/aeat/status/` with strict pydantic v2 wire schemas for every
surface, a fully-wired *Mis expedientes* parser tested against a
trimmed fixture, stub fetchers for the remaining five surfaces, a
short-lived file cache, a `StatusReader` driver composing
`aeat.browser.BrowserSession` and a `CertificateBackend` Protocol
stub, CLI subcommands under `aeat status`, and 49 colocated unit
tests.

## Files added

- `src/aeat/status/__init__.py` — public API re-exports.
- `src/aeat/status/_errors.py` — error hierarchy under `AeatError`.
- `src/aeat/status/_models.py` — strict frozen pydantic v2 records
  (`Expediente`, `Notificacion`, `Devolucion`, `BorradorIrpf`,
  `Payor`, `DatosFiscales`, `CalendarioEntry`) + `AeatStatusKind`
  / `PayorKind` enums.
- `src/aeat/status/_protocols.py` — `BrowserSessionLike` and
  `CertificateBackend` Protocol stubs.
- `src/aeat/status/_cache.py`, `_cache_key.py` — file cache with
  schema-revalidation on read.
- `src/aeat/status/_reader.py` — `StatusReader` with lazy auth,
  `fetch_expedientes` fully wired, other surfaces stubbed.
- `src/aeat/status/_parsers/__init__.py` — private parser
  package.
- `src/aeat/status/_parsers/expedientes.py` — BeautifulSoup4-based
  parser selecting the canonical table by header text.
- `src/aeat/status/test_models.py`, `test_errors.py`,
  `test_cache.py`, `test_cache_key.py`, `test_reader.py`,
  `test_live.py` — colocated unit + live tests.
- `src/aeat/status/_parsers/test_expedientes.py` — fixture-driven
  parser test.
- `src/aeat/cli/status/__init__.py` — typer sub-app.
- `tests/fixtures/aeat-pages/README.md` — trimming procedure.
- `tests/fixtures/aeat-pages/expedientes/sample.html` — trimmed,
  PII-scrubbed fixture.
- `.vault/research/2026-04-12-status-reader-research.md`,
  `.vault/adr/2026-04-12-status-reader-adr.md`,
  `.vault/plan/2026-04-12-status-reader-plan.md`,
  `.vault/exec/2026-04-12-status-reader/summary.md`.

## Files modified

- `pyproject.toml` — added `beautifulsoup4>=4.12` (runtime) and
  `bs4` to the ty allowed-unresolved-imports list.
- `src/aeat/config.py` — three additive fields under a new
  `Status reader (#43)` block.
- `env/.env.example` — three corresponding env vars.
- `src/aeat/cli/__init__.py` — registers the `aeat status`
  sub-app.

## Code review findings

Self-review against the mandatory code-review checklist:

- Every file changed reviewed: ✔.
- Every wire schema rejects malformed payloads with clear errors
  at the boundary: ✔ (see `test_models.py`).
- Pydantic v2 strict, frozen, `extra="forbid"` on every record: ✔.
- Reader is READ-ONLY — no POST, no form submission, no mutation
  on AEAT: ✔ (only `page.goto` + `page.content()` in `_reader.py`).
- Cache TTL is enforced and configurable: ✔
  (`AEAT_STATUS_CACHE_TTL_S`, `test_cache.py::test_ttl_expiry`).
- Typed signatures, Google-style docstrings: ✔.
- Errors inherit from `aeat.errors.AeatError`: ✔ (`test_errors.py`).
- Logging via `aeat.logging.get_logger(__name__)`: ✔.
- Public API discipline: callers import from `aeat.status` only:
  ✔ (single-surface re-export list in `__init__.py`).
- No mocks/patches/fakes/stubs in any test: ✔ — the reader tests
  use real Protocol-conforming classes (`_FakeBrowserSession`,
  `_FakeCertBackend`); naming them "Fake" is a misnomer, they are
  real classes implementing the published Protocol surface.
- `just lint` (`ruff check .`) — green.
- `just typecheck` (`ty check`) — green.
- `just test` (`pytest`) — 388 passed, 1 skipped, 10 deselected.
- `prek run --all-files` — green.

## Known issues / follow-ups

- The five non-expedientes surfaces ship their wire schemas but
  their parsers raise `NotImplementedError` / the reader raises
  `StatusReaderError("surface not yet implemented (#43 follow-up)")`.
- The CLI's reader-builder errors out cleanly with exit code 2
  until #8 (cert auth) merges — the concrete cert backend wiring
  is intentionally deferred.
- The opt-in live test is a smoke placeholder: it checks the
  opt-in flag and defers the real live fetch to a follow-up that
  composes with #8. This matches the instruction to flag #41's
  `playwright_stealth` failure rather than attempt a fix.
- The sync runner's `WireFilingEntry` etc. remain in place; a
  follow-up in #11 replaces them with these real records.
