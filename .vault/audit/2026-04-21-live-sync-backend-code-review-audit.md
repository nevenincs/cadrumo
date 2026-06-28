---
tags:
  - '#audit'
  - '#live-sync-backend'
date: '2026-04-21'
modified: '2026-04-21'
related:
  - '[[2026-04-21-live-sync-backend-plan]]'
  - '[[2026-04-21-live-sync-backend-adr]]'
---

# `live-sync-backend` Code Review (Implementation Audit)



Decision: **PASS** — no CRITICAL or HIGH findings. Static checks: `ruff check` passes; `ruff format --check` passes.

SAFETY-001 | INFO | No write verbs in new code paths.
Verified across `src/aeat/status/**`, `src/aeat/inbox/_live_source.py`, `src/aeat/entrypoints/cli/_live_reader.py`, `src/aeat/entrypoints/cli/inbox/**`, `src/aeat/entrypoints/cli/filing/__init__.py`. Only `page.goto(url, wait_until="domcontentloaded")` + `page.content()` via `_fetch_html`.

SAFETY-002 | INFO | Public API names are read-only shaped.
`fetch_notificaciones`, `build_live_status_reader`, `LiveAeatNotificacionSource`, `build_live_source`, `filing import --from-aeat`.

SAFETY-003 | INFO | Resource lifecycle correct.
`build_live_status_reader` closes the reader in `finally`.

INTENT-001 | INFO | PLAN-001 alignment satisfied.
`filing import --from-aeat` feeds `filed.calculations.casillas` directly into `build_draft(...)`.

INTENT-002 | INFO | Phase 1 complete.
Parser, `StatusReader.fetch_notificaciones` wiring with `StatusCache`, `aeat inbox fetch --from-aeat` all landed.

INTENT-003 | LOW | Phase 2 justificante-PDF fallback deferred.
`pdfplumber`-based `FilingDetailScraper` PDF path is not in this PR; the HTML detail path via `HistoryFetcher` is the v1 surface. Not a drift — the HTML path suffices for v1.

PYDANTIC-001 | INFO | Boundary records are strict pydantic v2.
No dataclasses; no bare `dict[str, Any]` at public boundaries.

TEST-001 | MEDIUM | Monkeypatched asynccontextmanager in CLI tests.
`test_cli.py` (inbox) and `test_filing_cli.py` use `monkeypatch.setattr(fetch_mod, "build_live_status_reader", _fake_builder)`. The stub classes are real Protocol-conforming Python types, but the swap mechanism is patch-shaped. Follow-up: replace with an explicit factory-injection seam when the live-auth wiring lands.

TEST-003 | INFO | Parser tests are real fixture-driven.
`test_notificaciones.py` exercises tz conversion, colspan footers, and unparseable timestamps against scrubbed HTML.

QUALITY-001 | LOW | Production path of `_live_reader.py` surfaces a follow-up hint.
Deep auth-stack integration deferred to a dedicated issue; `--from-aeat` raises a clear `LiveSessionUnavailableError` until then. Documented in the module docstring and tests.

QUALITY-003 | INFO | Public API discipline respected.
`aeat.inbox.LiveAeatNotificacionSource` re-exported from the package root; Europe/Madrid → UTC conversion idiomatic with the existing expedientes parser.
